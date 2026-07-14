from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_session_factory


async def get_raw_db() -> AsyncIterator[AsyncSession]:
    """A plain DB session with no tenant scoping applied.

    Only for use where a tenant is not yet known (the auth dependency's API-key
    lookup) or where a query is intentionally cross-tenant (admin endpoints). Never
    use this to read/write documents, chunks, ingestion_jobs, or eval_runs -- use
    app.core.security.get_tenant_db for those.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
        await session.commit()
