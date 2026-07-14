import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.documents import DocumentResponse, UploadDocumentResponse
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.security import get_current_tenant_id_dep, get_tenant_db
from app.db.models.document import Document, DocumentStatus
from app.db.models.ingestion_job import IngestionJob, IngestionJobStatus
from app.ingestion.chunking import CHUNKING_CONFIG_VERSION
from app.ingestion.hashing import content_hash
from app.ingestion.loaders.registry import SUPPORTED_CONTENT_TYPES
from app.vectorstore.factory import build_vector_store
from app.worker.queue import get_arq_pool, ingestion_job_id

router = APIRouter(prefix="/documents", tags=["documents"])


async def _enqueue_ingestion(
    tenant_id: uuid.UUID, document_id: uuid.UUID, job_id: uuid.UUID, hash_: str
) -> None:
    pool = await get_arq_pool()
    await pool.enqueue_job(
        "ingest_document",
        str(tenant_id),
        str(document_id),
        str(job_id),
        _job_id=ingestion_job_id(document_id, hash_),
    )


@router.post("", response_model=UploadDocumentResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> UploadDocumentResponse:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise ValidationAppError(f"Unsupported content type: {content_type}")

    raw = await file.read()
    hash_ = content_hash(raw)
    source_identifier = file.filename or "unnamed"

    result = await db.execute(
        select(Document).where(
            Document.tenant_id == tenant_id, Document.source_identifier == source_identifier
        )
    )
    existing = result.scalar_one_or_none()

    if (
        existing is not None
        and existing.content_hash == hash_
        and existing.chunking_config_version == CHUNKING_CONFIG_VERSION
    ):
        return UploadDocumentResponse(
            document=DocumentResponse.model_validate(existing), ingestion_job_id=None, skipped=True
        )

    if existing is not None:
        existing.raw_content = raw
        existing.content_hash = hash_
        existing.content_type = content_type
        existing.chunking_config_version = CHUNKING_CONFIG_VERSION
        existing.status = DocumentStatus.PENDING
        document = existing
    else:
        document = Document(
            tenant_id=tenant_id,
            source_identifier=source_identifier,
            filename=source_identifier,
            content_type=content_type,
            content_hash=hash_,
            chunking_config_version=CHUNKING_CONFIG_VERSION,
            raw_content=raw,
            status=DocumentStatus.PENDING,
        )
        db.add(document)
    await db.flush()
    await db.refresh(document)

    job = IngestionJob(
        tenant_id=tenant_id, document_id=document.id, status=IngestionJobStatus.PENDING
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Enqueue only after the request's transaction has actually committed (which
    # happens when get_tenant_db's session.begin() block exits, after this handler
    # returns) -- otherwise the worker could pick up the job before the document/job
    # rows are visible to it. BackgroundTasks run after the response is sent, which
    # is safely after dependency cleanup.
    background_tasks.add_task(_enqueue_ingestion, tenant_id, document.id, job.id, hash_)

    return UploadDocumentResponse(
        document=DocumentResponse.model_validate(document), ingestion_job_id=job.id, skipped=False
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[Document]:
    result = await db.execute(
        select(Document).where(Document.tenant_id == tenant_id).order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
    db: AsyncSession = Depends(get_tenant_db),
) -> None:
    document = await db.get(Document, document_id)
    if document is None or document.tenant_id != tenant_id:
        raise NotFoundError(f"Document {document_id} not found")

    vector_store = build_vector_store(db)
    await vector_store.delete_by_document(tenant_id, document_id)
    await db.delete(document)
