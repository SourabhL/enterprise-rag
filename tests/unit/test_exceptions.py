import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from starlette.requests import Request

from app.core.exceptions import (
    NotFoundError,
    ProviderError,
    RateLimitExceededError,
    TenantMismatchError,
    UnauthorizedError,
    ValidationAppError,
    app_error_handler,
)


@pytest.mark.parametrize(
    ("exc_cls", "expected_status", "expected_code"),
    [
        (NotFoundError, 404, "not_found"),
        (UnauthorizedError, 401, "unauthorized"),
        (TenantMismatchError, 403, "tenant_mismatch"),
        (ValidationAppError, 422, "validation_error"),
        (RateLimitExceededError, 429, "rate_limit_exceeded"),
        (ProviderError, 502, "provider_error"),
    ],
)
def test_app_error_status_and_code(exc_cls, expected_status, expected_code):
    exc = exc_cls("boom")
    assert exc.status_code == expected_status
    assert exc.code == expected_code
    assert exc.message == "boom"


def _fake_request(**state: Any) -> Request:
    return cast(Request, SimpleNamespace(state=SimpleNamespace(**state)))


async def test_app_error_handler_returns_json_envelope():
    request = _fake_request(request_id="req-123")
    exc = NotFoundError("thing not found")

    response = await app_error_handler(request, exc)

    assert response.status_code == 404
    body = json.loads(bytes(response.body))
    assert body == {
        "error": {"code": "not_found", "message": "thing not found", "request_id": "req-123"}
    }


async def test_app_error_handler_handles_missing_request_id():
    request = _fake_request()
    response = await app_error_handler(request, ProviderError("upstream failed"))

    body = json.loads(bytes(response.body))
    assert body["error"]["request_id"] is None
