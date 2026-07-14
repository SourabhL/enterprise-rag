import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request

from app.api.router import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.require_provider_keys()
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise RAG Pipeline", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.middleware("http")
    async def bind_request_context(request: Request, call_next):  # noqa: ANN001, ANN202
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    return app


app = create_app()
