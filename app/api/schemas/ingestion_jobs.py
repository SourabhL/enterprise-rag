import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.ingestion_job import IngestionJobStatus


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: IngestionJobStatus
    error: str | None
    created_at: datetime
    updated_at: datetime
