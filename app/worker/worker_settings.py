from arq.connections import RedisSettings

from app.config import get_settings
from app.worker.tasks import MAX_TRIES, ingest_document


class WorkerSettings:
    functions = [ingest_document]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = MAX_TRIES
