from fastapi import APIRouter

from app.api.v1 import admin, documents, health, ingestion_jobs, query

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(admin.router, prefix="/v1")
api_router.include_router(documents.router, prefix="/v1")
api_router.include_router(ingestion_jobs.router, prefix="/v1")
api_router.include_router(query.router, prefix="/v1")
