import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestContextMiddleware:
    """Binds a request ID into structlog context and echoes it in the response.

    A pure ASGI middleware rather than the `@app.middleware("http")` /
    BaseHTTPMiddleware decorator form -- BaseHTTPMiddleware runs the downstream app
    in a separate anyio task, which is a documented source of "attached to a
    different loop" failures for code using SQLAlchemy's async+greenlet bridge
    (asyncpg connections) further down the stack.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Drop any existing x-request-id so downstream code can never cause
                # a duplicate header -- exactly one x-request-id, always ours.
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_request_id)
