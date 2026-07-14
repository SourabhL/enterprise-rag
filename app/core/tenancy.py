import uuid
from contextvars import ContextVar

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)


def set_current_tenant_id(tenant_id: uuid.UUID) -> None:
    """Binds the resolved tenant to this request's context, for logging/tracing only.
    DB-level isolation does NOT rely on this contextvar -- see app.db.session."""
    _current_tenant_id.set(tenant_id)


def get_current_tenant_id() -> uuid.UUID | None:
    return _current_tenant_id.get()
