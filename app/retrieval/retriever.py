import uuid

from app.providers.base import EmbeddingProvider
from app.vectorstore.base import ScoredChunk, VectorStore


class Retriever:
    """Tenant-scoped vector search: embeds the query and searches the vector store."""

    def __init__(
        self, embedding_provider: EmbeddingProvider, vector_store: VectorStore, top_k: int
    ):
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._top_k = top_k

    async def retrieve(self, tenant_id: uuid.UUID, query: str) -> list[ScoredChunk]:
        [query_embedding] = await self._embedding_provider.embed([query], input_type="query")
        return await self._vector_store.similarity_search(tenant_id, query_embedding, self._top_k)
