from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.models.chunk import validate_embedding_dimensions
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.require_provider_keys()
    validate_embedding_dimensions(settings)
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise RAG Pipeline", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router)
    app.add_middleware(RequestContextMiddleware)
    configure_tracing(app, get_settings())
    return app


app = create_app()
