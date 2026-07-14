import uuid

import pytest

from app.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.rate_limit import enforce_rate_limit


async def test_rate_limit_blocks_after_threshold():
    tenant_id = uuid.uuid4()
    limit = get_settings().rate_limit_requests_per_minute

    for _ in range(limit):
        await enforce_rate_limit(tenant_id)

    with pytest.raises(RateLimitExceededError):
        await enforce_rate_limit(tenant_id)


async def test_rate_limit_is_per_tenant():
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    limit = get_settings().rate_limit_requests_per_minute

    for _ in range(limit):
        await enforce_rate_limit(tenant_a)

    # Tenant B has its own independent counter.
    await enforce_rate_limit(tenant_b)
