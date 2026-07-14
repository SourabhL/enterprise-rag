"""Creates a demo tenant + API key against a running local API for manual testing.

Usage: docker compose run --rm api python scripts/seed_dev_data.py
"""

import asyncio
import os

import httpx


async def main() -> None:
    base_url = os.environ.get("SEED_API_URL", "http://api:8000")
    admin_key = os.environ["ADMIN_BOOTSTRAP_KEY"]
    headers = {"X-Admin-Key": admin_key}

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        tenant_resp = await client.post("/v1/admin/tenants", json={"name": "demo"}, headers=headers)
        tenant_resp.raise_for_status()
        tenant = tenant_resp.json()
        print(f"Created tenant: {tenant['id']} ({tenant['name']})")

        key_resp = await client.post(
            "/v1/admin/api-keys",
            json={"tenant_id": tenant["id"], "scopes": ["read", "write"]},
            headers=headers,
        )
        key_resp.raise_for_status()
        key = key_resp.json()
        print(f"API key (save this, shown once): {key['api_key']}")


if __name__ == "__main__":
    asyncio.run(main())
