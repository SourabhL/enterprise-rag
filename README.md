# Enterprise RAG Pipeline

A multi-tenant, provider-agnostic Retrieval-Augmented Generation pipeline built on
FastAPI, Postgres/pgvector, and pluggable LLM/embedding providers (Anthropic Claude +
Voyage AI by default).

## Quickstart

```bash
cp .env.example .env               # fill in ANTHROPIC_API_KEY, VOYAGE_API_KEY, etc.
make up                            # docker compose up + wait for healthy
make migrate                       # alembic upgrade head
make seed                          # creates a demo tenant + prints an API key
```

Then query the API at `http://localhost:8000` using the printed API key as a bearer
token. See `docker-compose.yml` for the service topology (`postgres`, `redis`, `api`,
`worker`).

## Architecture

- **`app/providers/`** -- pluggable `LLMProvider` / `EmbeddingProvider` interfaces.
  Ships with Anthropic (generation) and Voyage AI / OpenAI (embeddings).
- **`app/vectorstore/`** -- `VectorStore` interface, backed by Postgres + pgvector.
- **`app/ingestion/`** -- document loaders (PDF/DOCX/HTML/TXT), chunking, and an async
  ingestion pipeline (arq/Redis-backed workers).
- **`app/retrieval/`** + **`app/generation/`** -- tenant-scoped vector retrieval and
  cited answer generation.
- **Multi-tenancy** -- every tenant-scoped table is filtered by `tenant_id` at the
  application layer *and* protected by Postgres row-level security as a
  defense-in-depth layer. See `app/core/security.py` and
  `migrations/versions/0002_pgvector_indexes_rls.py`.
- **Observability** -- structured JSON logs, OpenTelemetry tracing, Prometheus metrics,
  and a golden-set eval harness (`app/observability/`).

## Development

```bash
uv sync --all-extras --dev
make lint
make test
```
