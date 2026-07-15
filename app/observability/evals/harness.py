import asyncio
import uuid
from dataclasses import asdict, dataclass

from app.config import Settings
from app.db.models.document import Document, DocumentStatus
from app.db.models.tenant import Tenant
from app.db.session import get_raw_db, tenant_session
from app.generation.service import RAGService
from app.ingestion.chunking import CHUNKING_CONFIG_VERSION
from app.ingestion.hashing import content_hash
from app.ingestion.pipeline import IngestionPipeline
from app.logging_config import get_logger
from app.observability.evals.golden_dataset import GoldenExample
from app.observability.evals.scorers import score_groundedness, score_relevance
from app.providers.base import EmbeddingProvider, LLMProvider
from app.retrieval.reranker import NoOpReranker
from app.retrieval.retriever import Retriever
from app.vectorstore.factory import build_vector_store

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExampleResult:
    question: str
    answer: str | None
    retrieved_correct_document: bool
    groundedness: int
    relevance: int
    error: str | None = None


class EvalHarness:
    """Ingests each golden example's document into its own fresh scratch tenant,
    runs it through the real retrieval+generation pipeline, and scores retrieval
    recall plus LLM-judged groundedness/relevance.

    Each example gets its own scratch tenant (rather than one shared tenant for the
    whole run) so that one example's document can never be retrieved for another
    example's question -- with a shared tenant, a small golden set can easily have
    semantically-similar fixtures that contaminate each other's recall/groundedness
    scores. Scratch tenants and their documents are never cleaned up (out of scope
    for this pass, same as other v1 simplifications) -- acceptable for a low-volume
    eval feature, but worth revisiting if eval volume grows.

    Deliberately does not persist an EvalRun here -- ingesting fixture content into
    a tenant the caller doesn't own means the caller's own tenant must never be used
    for the underlying documents/chunks, but the summary itself has no such
    constraint. Callers (the API endpoint, the CLI script) persist the returned
    summary under whichever tenant is appropriate for their context.
    """

    def __init__(
        self, settings: Settings, embedding_provider: EmbeddingProvider, llm_provider: LLMProvider
    ):
        self._settings = settings
        self._embedding_provider = embedding_provider
        self._llm_provider = llm_provider

    async def run(self, dataset: list[GoldenExample], dataset_name: str) -> dict:
        pipeline = IngestionPipeline(self._embedding_provider, self._settings)
        results: list[ExampleResult] = []

        for index, example in enumerate(dataset):
            try:
                scratch_tenant_id = await self._create_scratch_tenant(dataset_name, index)
                results.append(await self._run_example(pipeline, scratch_tenant_id, example))
            except Exception as exc:
                # Each example runs in its own scratch tenant/transaction, so one
                # example failing (e.g. a transient provider rate limit) can't
                # corrupt or roll back the others -- record it and keep going
                # rather than losing the whole batch's results to one bad example.
                logger.warning(
                    "eval_example_failed", dataset_name=dataset_name, index=index, error=str(exc)
                )
                results.append(
                    ExampleResult(
                        question=example.question,
                        answer=None,
                        retrieved_correct_document=False,
                        groundedness=0,
                        relevance=0,
                        error=str(exc),
                    )
                )

        return _summarize(results)

    async def _create_scratch_tenant(self, dataset_name: str, index: int) -> uuid.UUID:
        tenant_id = uuid.uuid4()
        async for db in get_raw_db():
            db.add(Tenant(id=tenant_id, name=f"eval-scratch:{dataset_name}:{index}:{tenant_id}"))
            await db.commit()
            break
        return tenant_id

    async def _run_example(
        self, pipeline: IngestionPipeline, tenant_id: uuid.UUID, example: GoldenExample
    ) -> ExampleResult:
        async with tenant_session(tenant_id) as session:
            raw_content = example.document_text.encode("utf-8")
            document = Document(
                tenant_id=tenant_id,
                source_identifier="eval-doc",
                filename=example.document_filename,
                content_type="text/plain",
                content_hash=content_hash(raw_content),
                chunking_config_version=CHUNKING_CONFIG_VERSION,
                raw_content=raw_content,
                status=DocumentStatus.PENDING,
            )
            session.add(document)
            await session.flush()
            await pipeline.ingest(session=session, tenant_id=tenant_id, document_id=document.id)

            retriever = Retriever(
                self._embedding_provider,
                build_vector_store(session),
                self._settings.retrieval_top_k,
            )
            service = RAGService(retriever, NoOpReranker(), self._llm_provider)
            rag_answer = await service.answer(tenant_id, example.question)
            retrieved_correct = any(c.document_id == document.id for c in rag_answer.chunks)

            context = "\n\n".join(c.text for c in rag_answer.chunks)
            groundedness, relevance = await asyncio.gather(
                score_groundedness(
                    self._llm_provider,
                    question=example.question,
                    answer=rag_answer.answer,
                    context=context,
                ),
                score_relevance(
                    self._llm_provider, question=example.question, answer=rag_answer.answer
                ),
            )

            return ExampleResult(
                question=example.question,
                answer=rag_answer.answer,
                retrieved_correct_document=retrieved_correct,
                groundedness=groundedness.score,
                relevance=relevance.score,
            )


def _summarize(results: list[ExampleResult]) -> dict:
    succeeded = [r for r in results if r.error is None]
    count = len(succeeded) or 1
    return {
        "examples": [asdict(r) for r in results],
        "failed_count": len(results) - len(succeeded),
        "recall_at_k": sum(r.retrieved_correct_document for r in succeeded) / count,
        "avg_groundedness": sum(r.groundedness for r in succeeded) / count,
        "avg_relevance": sum(r.relevance for r in succeeded) / count,
    }
