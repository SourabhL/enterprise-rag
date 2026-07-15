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


def ingestion_job_id(
    document_id: uuid.UUID, content_hash: str, chunking_config_version: str
) -> str:
    """Deterministic arq job id so duplicate enqueues for the same document content
    *and* the same chunking config collapse into one job instead of double-
    processing. chunking_config_version must be part of the key: a re-ingestion
    triggered purely by a chunking-config bump (content unchanged) needs a distinct
    job id from the prior ingestion, or arq's dedup treats it as already-enqueued
    and silently drops it, leaving the new IngestionJob row stuck PENDING forever."""
    return f"ingest:{document_id}:{content_hash}:{chunking_config_version}"
