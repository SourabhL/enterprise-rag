from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import Settings
from app.db.base import get_engine


def configure_tracing(app: FastAPI, settings: Settings) -> None:
    """No-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set -- tracing is opt-in so local
    dev and CI don't need a collector running. Auto-instruments FastAPI, SQLAlchemy
    (the Anthropic/Voyage SDKs and asyncpg sit on httpx/direct sockets respectively;
    httpx is instrumented, asyncpg spans come from SQLAlchemy's own instrumentation)."""
    if not settings.otel_exporter_otlp_endpoint:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=get_engine().sync_engine)
    HTTPXClientInstrumentor().instrument()
