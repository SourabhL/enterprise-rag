import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import NotFoundError
from app.db.models.document import Document, DocumentStatus
from app.ingestion.chunking import chunk_sections
from app.ingestion.loaders.registry import get_loader
from app.providers.base import EmbeddingProvider
from app.vectorstore.base import ChunkRecord
from app.vectorstore.factory import build_vector_store


class IngestionPipeline:
    def __init__(self, embedding_provider: EmbeddingProvider, settings: Settings):
        self._embedding_provider = embedding_provider
        self._chunk_size = settings.chunk_size
        self._chunk_overlap = settings.chunk_overlap

    async def ingest(
        self, *, session: AsyncSession, tenant_id: uuid.UUID, document_id: uuid.UUID
    ) -> int:
        """Loads, chunks, embeds, and upserts one document's chunks. Returns the
        resulting chunk count. Re-ingestion is idempotent: existing chunks for the
        document are replaced transactionally, keyed off the caller's decision to
        invoke this at all (see documents API's content-hash comparison)."""
        document = await session.get(Document, document_id)
        if document is None or document.tenant_id != tenant_id:
            raise NotFoundError(f"Document {document_id} not found")

        document.status = DocumentStatus.PROCESSING
        await session.flush()

        loader = get_loader(document.content_type)
        sections = loader.load(document.raw_content)
        chunks = chunk_sections(
            sections, chunk_size=self._chunk_size, chunk_overlap=self._chunk_overlap
        )

        vector_store = build_vector_store(session)
        await vector_store.delete_by_document(tenant_id, document_id)

        if chunks:
            embeddings = await self._embedding_provider.embed(
                [c.text for c in chunks], input_type="document"
            )
            records = [
                ChunkRecord(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    chunk_index=chunk.index,
                    text=chunk.text,
                    embedding=embedding,
                    metadata=chunk.metadata,
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ]
            await vector_store.upsert_chunks(tenant_id, records)
        else:
            records = []

        document.status = DocumentStatus.READY
        document.chunk_count = len(records)
        await session.flush()
        return len(records)
