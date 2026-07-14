import hashlib
import secrets
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import Depends, Header
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.tenancy import set_current_tenant_id
from app.db.models.api_key import ApiKey
from app.db.session import get_raw_db, tenant_session

API_KEY_PREFIX_LEN = 8
RAW_KEY_BYTES = 32


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, prefix, key_hash). Only raw_key is ever shown to the caller."""
    raw_key = f"erag_{secrets.token_urlsafe(RAW_KEY_BYTES)}"
    prefix = raw_key[:API_KEY_PREFIX_LEN]
    key_hash = hash_api_key(raw_key)
    return raw_key, prefix, key_hash


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


async def get_current_tenant_id_dep(
    authorization: str = Header(..., description="Bearer <api_key>"),
    db: AsyncSession = Depends(get_raw_db),
) -> uuid.UUID:
    """Resolves the caller's tenant strictly from the API key. tenant_id is never
    accepted from the request body/query params, which prevents spoofing."""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")
    raw_key = authorization.removeprefix("Bearer ").strip()
    if len(raw_key) < API_KEY_PREFIX_LEN:
        raise UnauthorizedError("Invalid API key")

    prefix = raw_key[:API_KEY_PREFIX_LEN]
    key_hash = hash_api_key(raw_key)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise UnauthorizedError("Invalid or revoked API key")

    await db.execute(
        update(ApiKey).where(ApiKey.id == api_key.id).values(last_used_at=datetime.now(UTC))
    )
    await db.commit()

    set_current_tenant_id(api_key.tenant_id)
    return api_key.tenant_id


async def get_tenant_db(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id_dep),
) -> AsyncIterator[AsyncSession]:
    """A DB session scoped to the authenticated tenant (see app.db.session.tenant_session)."""
    async with tenant_session(tenant_id) as session:
        yield session


def require_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> None:
    from app.config import get_settings

    settings = get_settings()
    if not secrets.compare_digest(x_admin_key, settings.admin_bootstrap_key):
        raise UnauthorizedError("Invalid admin key")
