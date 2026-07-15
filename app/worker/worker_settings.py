from typing import Any

from arq.connections import RedisSettings

from app.config import get_settings
from app.db.models.chunk import validate_embedding_dimensions
from app.worker.tasks import MAX_TRIES, ingest_document


async def startup(ctx: dict[str, Any]) -> None:
    # The API's lifespan runs this same check, but the worker is a separate
    # process/entrypoint that never goes through app.main -- without its own check
    # here, a misconfigured embedding provider would silently ingest wrong-dimension
    # vectors until Postgres rejects the insert deep in the pipeline instead of
    # failing fast at process startup.
    validate_embedding_dimensions(get_settings())


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
    on_startup = startup
