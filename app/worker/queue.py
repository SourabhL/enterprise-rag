import uuid

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


def ingestion_job_id(document_id: uuid.UUID, content_hash: str) -> str:
    """Deterministic arq job id so duplicate enqueues for the same document content
    collapse into one job instead of double-processing."""
    return f"ingest:{document_id}:{content_hash}"
