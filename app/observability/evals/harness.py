import uuid
from dataclasses import asdict, dataclass

from app.config import Settings
from app.db.models.document import Document, DocumentStatus
from app.db.models.eval_run import EvalRun
from app.db.session import tenant_session
from app.generation.service import RAGService
from app.ingestion.chunking import CHUNKING_CONFIG_VERSION
from app.ingestion.hashing import content_hash
from app.ingestion.pipeline import IngestionPipeline
from app.observability.evals.golden_dataset import GoldenExample
from app.observability.evals.scorers import score_groundedness, score_relevance
from app.providers.base import EmbeddingProvider, LLMProvider
from app.retrieval.reranker import NoOpReranker
from app.retrieval.retriever import Retriever
from app.vectorstore.factory import build_vector_store


@dataclass(frozen=True)
class ExampleResult:
    question: str
    answer: str
    retrieved_correct_document: bool
    groundedness: int
    relevance: int


class EvalHarness:
    """Ingests each golden example's document into a scratch tenant, runs it
    through the real retrieval+generation pipeline, and scores retrieval recall
    plus LLM-judged groundedness/relevance."""

    def __init__(
        self, settings: Settings, embedding_provider: EmbeddingProvider, llm_provider: LLMProvider
    ):
        self._settings = settings
        self._embedding_provider = embedding_provider
        self._llm_provider = llm_provider

    async def run(
        self, dataset: list[GoldenExample], tenant_id: uuid.UUID, dataset_name: str
    ) -> tuple[uuid.UUID, dict]:
        pipeline = IngestionPipeline(self._embedding_provider, self._settings)
        results: list[ExampleResult] = []

        async with tenant_session(tenant_id) as session:
            for index, example in enumerate(dataset):
                raw_content = example.document_text.encode("utf-8")
                document = Document(
                    tenant_id=tenant_id,
                    source_identifier=f"eval:{dataset_name}:{index}",
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
                retrieved = await retriever.retrieve(tenant_id, example.question)
                retrieved_correct = any(c.document_id == document.id for c in retrieved)

                service = RAGService(retriever, NoOpReranker(), self._llm_provider)
                rag_answer = await service.answer(tenant_id, example.question)

                context = "\n\n".join(c.text for c in retrieved)
                groundedness = await score_groundedness(
                    self._llm_provider,
                    question=example.question,
                    answer=rag_answer.answer,
                    context=context,
                )
                relevance = await score_relevance(
                    self._llm_provider, question=example.question, answer=rag_answer.answer
                )

                results.append(
                    ExampleResult(
                        question=example.question,
                        answer=rag_answer.answer,
                        retrieved_correct_document=retrieved_correct,
                        groundedness=groundedness.score,
                        relevance=relevance.score,
                    )
                )

            summary = _summarize(results)
            eval_run = EvalRun(tenant_id=tenant_id, dataset_name=dataset_name, results=summary)
            session.add(eval_run)
            await session.flush()
            eval_run_id = eval_run.id

        return eval_run_id, summary


def _summarize(results: list[ExampleResult]) -> dict:
    count = len(results) or 1
    return {
        "examples": [asdict(r) for r in results],
        "recall_at_k": sum(r.retrieved_correct_document for r in results) / count,
        "avg_groundedness": sum(r.groundedness for r in results) / count,
        "avg_relevance": sum(r.relevance for r in results) / count,
    }
