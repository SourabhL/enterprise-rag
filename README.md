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

Then call the API at `http://localhost:8000` using the printed API key as a bearer
token:

```bash
API_KEY=erag_...   # from `make seed`

# Upload a document (PDF, DOCX, HTML, or plain text)
curl -X POST http://localhost:8000/v1/documents \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@./some-document.pdf"

# Poll ingestion status
curl http://localhost:8000/v1/ingestion-jobs/<job_id> \
  -H "Authorization: Bearer $API_KEY"

# Ask a question -- answer comes back with citations into the retrieved chunks
curl -X POST http://localhost:8000/v1/query \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
  -d '{"query": "What does the document say about X?"}'
```

See `docker-compose.yml` for the service topology (`postgres`, `redis`, `api`,
`worker`) and `docker-compose.observability.yml` for an optional local Jaeger stack.

## API surface

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /healthz`, `GET /readyz` | none | Liveness / readiness probes |
| `GET /metrics` | none | Prometheus metrics |
| `POST /v1/admin/tenants`, `POST /v1/admin/api-keys` | `X-Admin-Key` | Tenant/API-key provisioning |
| `POST /v1/documents`, `GET /v1/documents`, `DELETE /v1/documents/{id}` | API key | Upload/list/delete documents |
| `GET /v1/ingestion-jobs/{id}` | API key | Poll ingestion job status |
| `POST /v1/query`, `POST /v1/query/stream` | API key | Ask a question (sync JSON / SSE) |
| `POST /v1/evals/run`, `GET /v1/evals/{id}` | API key | Run/inspect the golden-set eval harness |

## Architecture

- **`app/providers/`** -- pluggable `LLMProvider` / `EmbeddingProvider` interfaces.
  Ships with Anthropic (generation, prompt-cached, streaming) and Voyage AI / OpenAI
  (embeddings), selected via `LLM_PROVIDER` / `EMBEDDING_PROVIDER` env vars.
- **`app/vectorstore/`** -- `VectorStore` interface, backed by Postgres + pgvector
  (cosine similarity, HNSW index).
- **`app/ingestion/`** -- document loaders (PDF/DOCX/HTML/TXT), chunking
  (`langchain-text-splitters`), and an async ingestion pipeline (arq/Redis-backed
  worker) with content-hash idempotency.
- **`app/retrieval/`** + **`app/generation/`** -- tenant-scoped vector retrieval, a
  no-op `Reranker` (interface ready for a real reranker later), and cited answer
  generation (`RAGService`).
- **Multi-tenancy** -- every tenant-scoped table is filtered by `tenant_id` at the
  application layer *and* protected by Postgres row-level security as a
  defense-in-depth layer. The API/worker connect as a restricted, non-superuser
  Postgres role (`docker/postgres/init.sh`) specifically because RLS is bypassed for
  superusers. See `app/core/security.py`, `app/db/session.py`, and
  `migrations/versions/0002_pgvector_indexes_rls.py`.
- **Auth** -- API keys (hashed, tenant-scoped bearer tokens); tenant identity is
  resolved server-side only, never accepted from the request body. A separate
  bootstrap key gates admin (tenant/key provisioning) endpoints.
- **Observability** -- structured JSON logs (tenant/request ID bound into every log
  line), Prometheus metrics (`/metrics`: latency histograms, per-tenant token counts,
  retrieval-quality proxy), and opt-in OpenTelemetry tracing (no-op unless
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set).
- **Evals** -- `app/observability/evals/`: golden Q&A fixtures run through the real
  pipeline and get scored on retrieval recall@k plus LLM-as-judge
  groundedness/relevance. Runnable via `make eval` or `POST /v1/evals/run`.

## Explicitly out of scope (see the design doc history for rationale)

SSO/SAML/RBAC UI, Kubernetes/Helm manifests, multi-region deployment, non-Postgres
vector store adapters (interface only), S3 object storage (raw bytes in Postgres for
v1), connector-based ingestion (Drive/Confluence/Slack -- direct upload only), a
wired-in reranker model, per-document ACLs within a tenant, billing/metering,
self-serve tenant signup.

## Development

```bash
uv sync --all-extras --dev
make lint          # ruff + mypy
make test          # unit tests only -- no external services required
```

### Running the full test suite

Unit tests (`tests/unit/`) have zero external dependencies and run anywhere. The
integration suite (`tests/integration/`) exercises the real FastAPI app against a
real Postgres + Redis (with fake LLM/embedding providers standing in for
Anthropic/Voyage), and needs `DATABASE_URL`, `MIGRATOR_DATABASE_URL`, `REDIS_URL`, and
`ADMIN_BOOTSTRAP_KEY` set -- see `.github/workflows/ci.yml` for the exact setup
against service containers, or point them at your local `make up` stack:

```bash
uv run pytest tests/unit           # no setup needed
uv run pytest tests/integration    # needs Postgres + Redis reachable, see above
```
