import httpx


async def test_run_eval_returns_scored_summary(client: httpx.AsyncClient, tenant):
    _, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}

    resp = await client.post(
        "/v1/evals/run",
        headers=headers,
        json={
            "dataset_name": "smoke-test",
            "examples": [
                {
                    "question": "What is the capital of France?",
                    "document_text": "The capital of France is Paris.",
                    "document_filename": "facts.txt",
                }
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["dataset_name"] == "smoke-test"
    assert body["results"]["failed_count"] == 0
    assert body["results"]["recall_at_k"] == 1.0
    assert body["results"]["avg_groundedness"] == 4.0
    assert body["results"]["avg_relevance"] == 4.0

    # The eval run record itself is retrievable under the caller's own tenant.
    get_resp = await client.get(f"/v1/evals/{body['id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == body["id"]


async def test_run_eval_does_not_pollute_callers_live_corpus(client: httpx.AsyncClient, tenant):
    """Eval fixture documents must never become retrievable by the caller's own
    real queries -- they're ingested into an isolated scratch tenant, not the
    caller's tenant. See app/observability/evals/harness.py."""
    tenant_id, api_key = tenant
    headers = {"Authorization": f"Bearer {api_key}"}

    secret_phrase = "The eval-only launch code is ZULU-4471."
    resp = await client.post(
        "/v1/evals/run",
        headers=headers,
        json={
            "dataset_name": "isolation-check",
            "examples": [
                {
                    "question": "What is the launch code?",
                    "document_text": secret_phrase,
                    "document_filename": "secret.txt",
                }
            ],
        },
    )
    assert resp.status_code == 201

    # The caller's own document list must not show the eval fixture document.
    docs_resp = await client.get("/v1/documents", headers=headers)
    assert docs_resp.json() == []

    # The caller's own real query must not retrieve/cite the eval fixture content.
    query_resp = await client.post(
        "/v1/query", headers=headers, json={"query": "What is the launch code?"}
    )
    assert query_resp.status_code == 200
    assert query_resp.json()["citations"] == []
