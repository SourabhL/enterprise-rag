import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateTenantRequest(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class CreateApiKeyRequest(BaseModel):
    tenant_id: uuid.UUID
    scopes: list[str] = ["read", "write"]


class CreateApiKeyResponse(BaseModel):
    id: uuid.UUID
    api_key: str
    prefix: str
    scopes: list[str]
