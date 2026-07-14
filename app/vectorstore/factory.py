from sqlalchemy.ext.asyncio import AsyncSession

from app.vectorstore.base import VectorStore
from app.vectorstore.pgvector_store import PgVectorStore


def build_vector_store(session: AsyncSession) -> VectorStore:
    return PgVectorStore(session)
