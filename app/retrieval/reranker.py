from typing import Protocol, runtime_checkable

from app.vectorstore.base import ScoredChunk


@runtime_checkable
class Reranker(Protocol):
    async def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]: ...


class NoOpReranker:
    """Passthrough default so RAGService always calls a reranker uniformly.
    Swap in a Voyage/Cohere reranker later without touching callers."""

    async def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        return chunks
