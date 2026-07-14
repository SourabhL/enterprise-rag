import uuid
from typing import Any

from arq import Retry

from app.config import get_settings
from app.db.models.ingestion_job import IngestionJob, IngestionJobStatus
from app.db.session import tenant_session
from app.ingestion.pipeline import IngestionPipeline
from app.providers.registry import get_embedding_provider

MAX_TRIES = 3


async def ingest_document(
    ctx: dict[str, Any], tenant_id: str, document_id: str, job_id: str
) -> None:
    settings = get_settings()
    pipeline = IngestionPipeline(get_embedding_provider(), settings)
    tenant_uuid = uuid.UUID(tenant_id)

    async with tenant_session(tenant_uuid) as session:
        job = await session.get(IngestionJob, uuid.UUID(job_id))
        if job is None:
            return
        job.status = IngestionJobStatus.RUNNING
        job.error = None
        await session.flush()

        try:
            await pipeline.ingest(
                session=session, tenant_id=tenant_uuid, document_id=uuid.UUID(document_id)
            )
            job.status = IngestionJobStatus.SUCCEEDED
        except Exception as exc:
            job_try = ctx.get("job_try", 1)
            if job_try < MAX_TRIES:
                # Leave the job RUNNING -- arq will re-invoke this function; the
                # backoff grows with each attempt (2s, 4s, 8s, ...).
                raise Retry(defer=2**job_try) from exc
            job.status = IngestionJobStatus.FAILED
            job.error = str(exc)
            raise
        finally:
            await session.flush()
