import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.ingestion_jobs import IngestionJobResponse
from app.core.exceptions import NotFoundError
from app.core.security import get_current_tenant_id_dep, get_tenant_db
from app.db.models.ingestion_job import IngestionJob

router = APIRouter(prefix="/ingestion-jobs", tags=["ingestion-jobs"])


@router.get("/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> IngestionJob:
    job = await db.get(IngestionJob, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise NotFoundError(f"Ingestion job {job_id} not found")
    return job
