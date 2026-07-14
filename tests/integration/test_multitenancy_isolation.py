import uuid

import httpx

from app.db.session import tenant_session
from app.vectorstore.factory import build_vector_store
from app.worker.tasks import ingest_document
from tests.integration.conftest import create_tenant_and_key


async def test_cross_tenant_chunk_isolation(client: httpx.AsyncClient):
    tenant_a_id, key_a = await create_tenant_and_key(client)
    tenant_b_id, key_b = await create_tenant_and_key(client)

    resp_a = await client.post(
        "/v1/documents",
        headers={"Authorization": f"Bearer {key_a}"},
        files={"file": ("a.txt", b"Tenant A secret: the launch code is ALPHA-9182.", "text/plain")},
    )
    body_a = resp_a.json()
    await ingest_document(
        {"job_try": 1}, tenant_a_id, body_a["document"]["id"], body_a["ingestion_job_id"]
    )

    resp_b = await client.post(
        "/v1/documents",
        headers={"Authorization": f"Bearer {key_b}"},
        files={"file": ("b.txt", b"Tenant B notes: the weather today is sunny.", "text/plain")},
    )
    body_b = resp_b.json()
    await ingest_document(
        {"job_try": 1}, tenant_b_id, body_b["document"]["id"], body_b["ingestion_job_id"]
    )

    # Sanity: tenant A can see its own chunk via its own scoped session.
    async with tenant_session(uuid.UUID(tenant_a_id)) as session_a:
        vs_a = build_vector_store(session_a)
        chunks_a = await vs_a.similarity_search(uuid.UUID(tenant_a_id), [0.5] * 1024, top_k=10)
    assert len(chunks_a) >= 1

    # Row-level security fails closed even against a *wrong* app-level tenant_id
    # argument: a session scoped to tenant B via SET LOCAL app.tenant_id must never
    # return tenant A's rows, regardless of what tenant_id is passed to the query.
    async with tenant_session(uuid.UUID(tenant_b_id)) as session_b:
        vs_b = build_vector_store(session_b)
        leaked = await vs_b.similarity_search(uuid.UUID(tenant_a_id), [0.5] * 1024, top_k=10)
    assert leaked == []

    # And the HTTP API's own retrieval for tenant B never surfaces tenant A's document.
    query_resp = await client.post(
        "/v1/query",
        headers={"Authorization": f"Bearer {key_b}"},
        json={"query": "What is the launch code?"},
    )
    assert query_resp.status_code == 200
    for citation in query_resp.json()["citations"]:
        assert citation["document_id"] != body_a["document"]["id"]


async def test_tenant_cannot_read_or_delete_other_tenants_document(client: httpx.AsyncClient):
    _, key_a = await create_tenant_and_key(client)
    _, key_b = await create_tenant_and_key(client)

    resp_a = await client.post(
        "/v1/documents",
        headers={"Authorization": f"Bearer {key_a}"},
        files={"file": ("private.txt", b"tenant A private content", "text/plain")},
    )
    document_id = resp_a.json()["document"]["id"]

    # Tenant B's document list must never include tenant A's document.
    list_resp = await client.get("/v1/documents", headers={"Authorization": f"Bearer {key_b}"})
    assert all(doc["id"] != document_id for doc in list_resp.json())

    # Tenant B cannot delete tenant A's document (app-level ownership check).
    delete_resp = await client.delete(
        f"/v1/documents/{document_id}", headers={"Authorization": f"Bearer {key_b}"}
    )
    assert delete_resp.status_code == 404

    # It's still there for tenant A.
    list_resp_a = await client.get("/v1/documents", headers={"Authorization": f"Bearer {key_a}"})
    assert any(doc["id"] == document_id for doc in list_resp_a.json())
