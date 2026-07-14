FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python .

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
ENV PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app ./app

USER appuser

CMD ["arq", "app.worker.worker_settings.WorkerSettings"]
