import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Settings
from app.db.base import Base

# Must match EMBEDDING_DIMENSIONS in migrations/versions/0002_pgvector_indexes_rls.py
# and app.config.Settings.embedding_dimensions -- checked at startup by every process
# that touches embeddings (see validate_embedding_dimensions below). This is a schema
# constant (fixed by the migration that created the column), not a runtime setting,
# so it must not depend on Settings() -- that would require DATABASE_URL/
# ADMIN_BOOTSTRAP_KEY just to import this module (e.g. in unit tests).
EMBEDDING_DIMENSIONS = 1024


def validate_embedding_dimensions(settings: Settings) -> None:
    """Fails fast if the configured embedding provider's output dimension doesn't
    match the pgvector column's fixed dimension. Call this at the startup of every
    process that produces embeddings (the API and the worker) -- a silent mismatch
    would otherwise only surface as an opaque pgvector insert error deep in the
    ingestion pipeline, in whichever process skips the check."""
    if settings.embedding_dimensions != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Configured embedding provider produces {settings.embedding_dimensions}-dim "
            f"vectors but the chunks.embedding column is {EMBEDDING_DIMENSIONS}-dim "
            "(app.db.models.chunk.EMBEDDING_DIMENSIONS). Changing embedding "
            "provider/model dimension requires a new migration and a full re-embed."
        )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
