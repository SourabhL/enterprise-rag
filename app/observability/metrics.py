import uuid

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.providers.base import Usage

HTTP_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status_code"],
)

RETRIEVAL_LATENCY = Histogram("retrieval_duration_seconds", "Vector retrieval latency in seconds")
GENERATION_LATENCY = Histogram(
    "generation_duration_seconds", "LLM generation latency in seconds"
)
INGESTION_LATENCY = Histogram(
    "ingestion_duration_seconds", "End-to-end document ingestion latency in seconds"
)

LLM_INPUT_TOKENS = Counter("llm_input_tokens_total", "LLM input tokens consumed", ["tenant_id"])
LLM_OUTPUT_TOKENS = Counter("llm_output_tokens_total", "LLM output tokens generated", ["tenant_id"])
LLM_CACHE_READ_TOKENS = Counter(
    "llm_cache_read_tokens_total", "LLM prompt-cache tokens read", ["tenant_id"]
)
LLM_CACHE_CREATION_TOKENS = Counter(
    "llm_cache_creation_tokens_total", "LLM prompt-cache tokens written", ["tenant_id"]
)

RETRIEVAL_HIT = Counter(
    "retrieval_high_similarity_total",
    "Queries whose top-1 result exceeded the similarity threshold (online proxy "
    "for retrieval quality -- true recall is measured offline by the eval harness)",
)
RETRIEVAL_MISS = Counter(
    "retrieval_low_similarity_total",
    "Queries whose top-1 result did not exceed the similarity threshold, or that "
    "returned no results at all",
)
RETRIEVAL_HIT_THRESHOLD = 0.5


def record_llm_usage(tenant_id: uuid.UUID, usage: Usage) -> None:
    labels = {"tenant_id": str(tenant_id)}
    LLM_INPUT_TOKENS.labels(**labels).inc(usage.input_tokens)
    LLM_OUTPUT_TOKENS.labels(**labels).inc(usage.output_tokens)
    LLM_CACHE_READ_TOKENS.labels(**labels).inc(usage.cache_read_input_tokens)
    LLM_CACHE_CREATION_TOKENS.labels(**labels).inc(usage.cache_creation_input_tokens)


def record_retrieval_quality(top_score: float | None) -> None:
    if top_score is not None and top_score >= RETRIEVAL_HIT_THRESHOLD:
        RETRIEVAL_HIT.inc()
    else:
        RETRIEVAL_MISS.inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
