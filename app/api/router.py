from fastapi import APIRouter

from app.api.v1 import admin, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(admin.router, prefix="/v1")
