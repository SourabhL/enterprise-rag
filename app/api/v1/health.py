from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_raw_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness probe -- no dependency calls."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_raw_db)) -> dict:
    """Readiness probe -- checks DB connectivity."""
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
