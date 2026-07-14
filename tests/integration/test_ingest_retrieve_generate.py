import httpx

from app.worker.tasks import ingest_document


async def test_ingest_retrieve_and_generate_with_citations(client: httpx.AsyncClient, tenant):
    tenant_id, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}
    content = b"The capital of France is Paris. Paris is famous for the Eiffel Tower."

    upload_resp = await client.post(
        "/v1/documents", headers=headers, files={"file": ("facts.txt", content, "text/plain")}
    )
    assert upload_resp.status_code == 202
    body = upload_resp.json()
    job_id = body["ingestion_job_id"]
    document_id = body["document"]["id"]
    assert body["document"]["status"] == "pending"

    # No live arq worker in the test process -- invoke the task function directly,
    # exactly as the worker would when it dequeues the job.
    await ingest_document({"job_try": 1}, tenant_id, document_id, job_id)

    job_resp = await client.get(f"/v1/ingestion-jobs/{job_id}", headers=headers)
    assert job_resp.json()["status"] == "succeeded"

    docs_resp = await client.get("/v1/documents", headers=headers)
    docs = docs_resp.json()
    assert docs[0]["status"] == "ready"
    assert docs[0]["chunk_count"] >= 1

    query_resp = await client.post(
        "/v1/query", headers=headers, json={"query": "What is the capital of France?"}
    )
    assert query_resp.status_code == 200
    payload = query_resp.json()
    assert payload["answer"]
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["document_id"] == document_id


async def test_reupload_unchanged_content_is_skipped(client: httpx.AsyncClient, tenant):
    _, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}
    content = b"stable content"

    first = await client.post(
        "/v1/documents", headers=headers, files={"file": ("stable.txt", content, "text/plain")}
    )
    second = await client.post(
        "/v1/documents", headers=headers, files={"file": ("stable.txt", content, "text/plain")}
    )

    assert first.json()["skipped"] is False
    assert second.json()["skipped"] is True
    assert second.json()["ingestion_job_id"] is None
    assert second.json()["document"]["id"] == first.json()["document"]["id"]


async def test_delete_document_removes_chunks(client: httpx.AsyncClient, tenant):
    tenant_id, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}

    upload_resp = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("todelete.txt", b"some content to delete", "text/plain")},
    )
    body = upload_resp.json()
    await ingest_document(
        {"job_try": 1}, tenant_id, body["document"]["id"], body["ingestion_job_id"]
    )

    delete_resp = await client.delete(f"/v1/documents/{body['document']['id']}", headers=headers)
    assert delete_resp.status_code == 204

    docs_resp = await client.get("/v1/documents", headers=headers)
    assert docs_resp.json() == []


async def test_query_stream_returns_deltas_and_final_event(client: httpx.AsyncClient, tenant):
    tenant_id, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}
    upload_resp = await client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("stream.txt", b"streaming content example", "text/plain")},
    )
    body = upload_resp.json()
    await ingest_document(
        {"job_try": 1}, tenant_id, body["document"]["id"], body["ingestion_job_id"]
    )

    async with client.stream(
        "POST", "/v1/query/stream", headers=headers, json={"query": "example question"}
    ) as resp:
        assert resp.status_code == 200
        raw = ""
        async for chunk in resp.aiter_text():
            raw += chunk

    assert "event: delta" in raw
    assert "event: done" in raw
