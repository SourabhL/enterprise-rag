import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.observability.metrics import (
    GENERATION_LATENCY,
    RETRIEVAL_LATENCY,
    record_llm_usage,
    record_retrieval_quality,
)
from app.providers.base import LLMProvider, LLMStreamEvent, Message, Usage
from app.providers.registry import get_embedding_provider, get_llm_provider
from app.retrieval.prompt import SYSTEM_PROMPT, Citation, build_user_message, extract_citations
from app.retrieval.reranker import NoOpReranker, Reranker
from app.retrieval.retriever import Retriever
from app.vectorstore.base import ScoredChunk
from app.vectorstore.factory import build_vector_store

DEFAULT_MAX_TOKENS = 2048


@dataclass(frozen=True)
class RAGAnswer:
    answer: str
    citations: list[Citation]
    usage: Usage
    chunks: list[ScoredChunk]


class RAGService:
    def __init__(self, retriever: Retriever, reranker: Reranker, llm_provider: LLMProvider):
        self._retriever = retriever
        self._reranker = reranker
        self._llm_provider = llm_provider

    async def _retrieve(self, tenant_id: uuid.UUID, query: str) -> list[ScoredChunk]:
        start = time.monotonic()
        chunks = await self._retriever.retrieve(tenant_id, query)
        chunks = await self._reranker.rerank(query, chunks)
        RETRIEVAL_LATENCY.observe(time.monotonic() - start)
        record_retrieval_quality(chunks[0].score if chunks else None)
        return chunks

    async def answer(self, tenant_id: uuid.UUID, query: str) -> RAGAnswer:
        chunks = await self._retrieve(tenant_id, query)
        start = time.monotonic()
        response = await self._llm_provider.generate(
            system=SYSTEM_PROMPT,
            messages=[Message(role="user", content=build_user_message(query, chunks))],
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        GENERATION_LATENCY.observe(time.monotonic() - start)
        record_llm_usage(tenant_id, response.usage)
        return RAGAnswer(
            answer=response.text,
            citations=extract_citations(response.text, chunks),
            usage=response.usage,
            chunks=chunks,
        )

    async def answer_stream(
        self, tenant_id: uuid.UUID, query: str
    ) -> tuple[list[ScoredChunk], AsyncIterator[LLMStreamEvent]]:
        """Returns the retrieved chunks (needed to compute citations once the full
        text is known) alongside the raw stream events."""
        chunks = await self._retrieve(tenant_id, query)
        stream = self._llm_provider.stream(
            system=SYSTEM_PROMPT,
            messages=[Message(role="user", content=build_user_message(query, chunks))],
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        return chunks, stream


def build_rag_service(session: AsyncSession, settings: Settings) -> RAGService:
    vector_store = build_vector_store(session)
    retriever = Retriever(get_embedding_provider(), vector_store, settings.retrieval_top_k)
    return RAGService(retriever, NoOpReranker(), get_llm_provider())
