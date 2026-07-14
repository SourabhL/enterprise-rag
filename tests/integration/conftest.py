import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

import app.core.rate_limit as rate_limit_module
import app.db.base as db_base
import app.worker.queue as worker_queue
from app.main import app
from app.providers.base import LLMResponse, LLMStreamEvent, Message, Usage

ADMIN_KEY = "changeme-root-key"


@pytest_asyncio.fixture(autouse=True)
async def reset_async_singletons():
    """app.db.base's engine, the arq pool, and the Redis client are module-level
    singletons bound to whichever event loop first creates them. pytest-asyncio
    gives each test function its own loop by default, so a singleton created in
    test A's loop breaks on first use in test B ("attached to a different loop").
    Reset them before/after every test so each test creates its own, bound to its
    own loop."""
    db_base._engine = None
    db_base._session_factory = None
    worker_queue._pool = None
    rate_limit_module._redis = None
    yield
    if db_base._engine is not None:
        await db_base._engine.dispose()
    db_base._engine = None
    db_base._session_factory = None
    worker_queue._pool = None
    rate_limit_module._redis = None


class FakeEmbeddingProvider:
    """Deterministic, content-derived embeddings -- no network calls, but the
    identical-text-gets-identical-vector property still exercises real pgvector
    nearest-neighbor ranking meaningfully."""

    model_name = "fake-embed"
    dimensions = 1024

    async def embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        vectors = []
        for text in texts:
            seed = sum(text.encode("utf-8")) or 1
            vectors.append([((seed * (i + 1)) % 997) / 997 for i in range(self.dimensions)])
        return vectors


class FakeLLMProvider:
    model_name = "fake-llm"

    async def generate(
        self, *, system: str, messages: list[Message], max_tokens: int, effort: str = "high"
    ) -> LLMResponse:
        text = "Based on [S1], the answer is derived from the retrieved context."
        return LLMResponse(text=text, usage=Usage(input_tokens=50, output_tokens=20))

    async def stream(self, *, system: str, messages: list[Message], max_tokens: int):
        for piece in ["Based on ", "[S1], ", "the answer follows."]:
            yield LLMStreamEvent(delta=piece)
        yield LLMStreamEvent(
            delta="", is_final=True, usage=Usage(input_tokens=50, output_tokens=20)
        )


@pytest.fixture(autouse=True)
def patch_providers(monkeypatch):
    # Each call site did `from app.providers.registry import get_..._provider`, which
    # binds its own name in that module's namespace -- patching the attribute on
    # provider_registry itself does not affect those already-bound names, so every
    # import site needs to be patched individually.
    for target in (
        "app.providers.registry.get_embedding_provider",
        "app.worker.tasks.get_embedding_provider",
        "app.generation.service.get_embedding_provider",
    ):
        monkeypatch.setattr(target, lambda: FakeEmbeddingProvider())
    for target in (
        "app.providers.registry.get_llm_provider",
        "app.generation.service.get_llm_provider",
    ):
        monkeypatch.setattr(target, lambda: FakeLLMProvider())


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def create_tenant_and_key(client: httpx.AsyncClient) -> tuple[str, str]:
    tenant_resp = await client.post(
        "/v1/admin/tenants",
        json={"name": f"test-tenant-{uuid.uuid4()}"},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    tenant_resp.raise_for_status()
    tenant_id = tenant_resp.json()["id"]

    key_resp = await client.post(
        "/v1/admin/api-keys",
        json={"tenant_id": tenant_id},
        headers={"X-Admin-Key": ADMIN_KEY},
    )
    key_resp.raise_for_status()
    return tenant_id, key_resp.json()["api_key"]


@pytest_asyncio.fixture
async def tenant_api_key(client: httpx.AsyncClient) -> str:
    _, api_key = await create_tenant_and_key(client)
    return api_key


@pytest_asyncio.fixture
async def tenant(client: httpx.AsyncClient) -> tuple[str, str]:
    return await create_tenant_and_key(client)
