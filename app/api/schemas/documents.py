import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.document import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    ingestion_job_id: uuid.UUID | None
    skipped: bool
