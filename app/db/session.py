import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory


async def get_raw_db() -> AsyncIterator[AsyncSession]:
    """A plain DB session with no tenant scoping applied.

    Only for use where a tenant is not yet known (the auth dependency's API-key
    lookup) or where a query is intentionally cross-tenant (admin endpoints). Never
    use this to read/write documents, chunks, ingestion_jobs, or eval_runs -- use
    tenant_session/app.core.security.get_tenant_db for those.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
        await session.commit()


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A DB session scoped to one tenant for the lifetime of the transaction.

    Issues `SELECT set_config('app.tenant_id', ..., true)` (transaction-scoped, same
    effect as `SET LOCAL`, but -- unlike `SET LOCAL` -- supports bind parameters) so
    Postgres RLS policies enforce isolation as a defense-in-depth layer alongside the
    explicit `WHERE tenant_id = ...` filtering application code must still apply.
    Used both by the FastAPI get_tenant_db dependency and by background workers,
    which have no request/dependency chain to resolve a session through.
    """
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            yield session
