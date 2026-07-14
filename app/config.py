from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    database_url: str
    # Elevated connection used only by Alembic for DDL/GRANTs. The API/worker never
    # use this -- they connect via database_url as the restricted `rag_app` role so
    # that Postgres RLS policies actually apply (RLS is bypassed for superusers).
    migrator_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["anthropic"] = "anthropic"
    embedding_provider: Literal["voyage", "openai"] = "voyage"

    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"

    voyage_api_key: str = ""
    voyage_embedding_model: str = "voyage-3-large"
    voyage_embedding_dimensions: int = 1024

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimensions: int = 1024

    admin_bootstrap_key: str = Field(min_length=8)

    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "enterprise-rag-api"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 8

    rate_limit_requests_per_minute: int = 60

    @property
    def embedding_dimensions(self) -> int:
        if self.embedding_provider == "openai":
            return self.openai_embedding_dimensions
        return self.voyage_embedding_dimensions

    def require_provider_keys(self) -> None:
        """Fail fast at startup if the configured providers are missing credentials."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        if self.embedding_provider == "voyage" and not self.voyage_api_key:
            raise ValueError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage")
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
