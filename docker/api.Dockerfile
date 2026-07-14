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
COPY migrations ./migrations
COPY alembic.ini ./

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
