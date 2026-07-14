from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.admin import (
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    CreateTenantRequest,
    TenantResponse,
)
from app.core.exceptions import NotFoundError
from app.core.security import generate_api_key, require_admin_key
from app.db.models.api_key import ApiKey
from app.db.models.tenant import Tenant
from app.db.session import get_raw_db

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


@router.post("/tenants", response_model=TenantResponse, status_code=201)
async def create_tenant(
    body: CreateTenantRequest, db: AsyncSession = Depends(get_raw_db)
) -> Tenant:
    tenant = Tenant(name=body.name)
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


@router.post("/api-keys", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest, db: AsyncSession = Depends(get_raw_db)
) -> CreateApiKeyResponse:
    tenant = await db.get(Tenant, body.tenant_id)
    if tenant is None:
        raise NotFoundError(f"Tenant {body.tenant_id} not found")

    raw_key, prefix, key_hash = generate_api_key()
    api_key = ApiKey(tenant_id=tenant.id, key_hash=key_hash, prefix=prefix, scopes=body.scopes)
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    return CreateApiKeyResponse(
        id=api_key.id, api_key=raw_key, prefix=prefix, scopes=api_key.scopes
    )
