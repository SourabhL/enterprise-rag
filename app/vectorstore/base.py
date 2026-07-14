import uuid
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ChunkRecord:
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    text: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    async def upsert_chunks(self, tenant_id: uuid.UUID, chunks: list[ChunkRecord]) -> None: ...

    async def similarity_search(
        self,
        tenant_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[ScoredChunk]: ...

    async def delete_by_document(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> None: ...
