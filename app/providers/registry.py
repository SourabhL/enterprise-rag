from functools import lru_cache

from app.config import Settings, get_settings
from app.db.models.chunk import validate_embedding_dimensions
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.providers.embeddings.voyage_provider import VoyageEmbeddingProvider
from app.providers.llm.anthropic_provider import AnthropicLLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        return AnthropicLLMProvider(settings)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "voyage":
        return VoyageEmbeddingProvider(settings)
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(settings)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    # The API and worker also validate this at process startup (fail fast before
    # serving any traffic) -- this call is the safety net for every other entrypoint
    # (scripts, one-off tooling) that constructs an embedding provider without going
    # through either startup hook.
    settings = get_settings()
    validate_embedding_dimensions(settings)
    return build_embedding_provider(settings)
