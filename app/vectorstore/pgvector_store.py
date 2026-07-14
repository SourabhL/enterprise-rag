import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.chunk import Chunk
from app.vectorstore.base import ChunkRecord, ScoredChunk


class PgVectorStore:
    """Postgres + pgvector implementation of VectorStore.

    Takes the caller's tenant-scoped AsyncSession (see app.core.security.get_tenant_db)
    so writes/reads happen inside the same RLS-scoped transaction as everything else in
    the request. Every query still applies an explicit tenant_id filter -- RLS is
    defense-in-depth, not a substitute for application-level scoping.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_chunks(self, tenant_id: uuid.UUID, chunks: list[ChunkRecord]) -> None:
        if not chunks:
            return
        stmt = insert(Chunk).values(
            [
                {
                    "id": c.id,
                    "tenant_id": tenant_id,
                    "document_id": c.document_id,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "embedding": c.embedding,
                    "chunk_metadata": c.metadata,
                }
                for c in chunks
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Chunk.document_id, Chunk.chunk_index],
            set_={
                "text": stmt.excluded.text,
                "embedding": stmt.excluded.embedding,
                "chunk_metadata": stmt.excluded.chunk_metadata,
            },
        )
        await self._session.execute(stmt)

    async def similarity_search(
        self,
        tenant_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
    ) -> list[ScoredChunk]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(Chunk, distance.label("distance"))
            .where(Chunk.tenant_id == tenant_id)
            .order_by(distance)
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        return [
            ScoredChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                score=1.0 - distance_value,
                metadata=chunk.chunk_metadata,
            )
            for chunk, distance_value in result.all()
        ]

    async def delete_by_document(self, tenant_id: uuid.UUID, document_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(Chunk).where(Chunk.tenant_id == tenant_id, Chunk.document_id == document_id)
        )
