import uuid
from typing import Any

from arq import Retry

from app.config import get_settings
from app.db.models.ingestion_job import IngestionJob, IngestionJobStatus
from app.db.session import tenant_session
from app.ingestion.pipeline import IngestionPipeline
from app.providers.registry import get_embedding_provider

MAX_TRIES = 3


async def _set_job_status(
    tenant_id: uuid.UUID, job_id: uuid.UUID, status: IngestionJobStatus, error: str | None = None
) -> None:
    """Writes the job status in its own transaction, independent of the ingestion
    work's transaction. This matters because tenant_session's `session.begin()`
    rolls back the *entire* transaction when an exception propagates out of it --
    if the terminal FAILED status were written in the same transaction as the
    ingestion attempt and then the caller re-raised to signal the failure, that
    status write would be rolled back along with everything else, leaving the job
    stuck showing a stale status forever."""
    async with tenant_session(tenant_id) as session:
        job = await session.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = status
        job.error = error


async def ingest_document(
    ctx: dict[str, Any], tenant_id: str, document_id: str, job_id: str
) -> None:
    settings = get_settings()
    pipeline = IngestionPipeline(get_embedding_provider(), settings)
    tenant_uuid = uuid.UUID(tenant_id)
    job_uuid = uuid.UUID(job_id)

    await _set_job_status(tenant_uuid, job_uuid, IngestionJobStatus.RUNNING)

    try:
        async with tenant_session(tenant_uuid) as session:
            await pipeline.ingest(
                session=session, tenant_id=tenant_uuid, document_id=uuid.UUID(document_id)
            )
    except Exception as exc:
        job_try = ctx.get("job_try", 1)
        if job_try < MAX_TRIES:
            # arq will re-invoke this function; the backoff grows with each
            # attempt (2s, 4s, 8s, ...). Job status stays RUNNING in the meantime.
            raise Retry(defer=2**job_try) from exc
        await _set_job_status(tenant_uuid, job_uuid, IngestionJobStatus.FAILED, error=str(exc))
        raise
    else:
        await _set_job_status(tenant_uuid, job_uuid, IngestionJobStatus.SUCCEEDED)
