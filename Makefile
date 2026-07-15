.PHONY: up down logs migrate seed test test-integration lint fmt eval

up:
	docker compose up -d --build
	@echo "Waiting for API to become healthy..."
	@until curl -sf http://localhost:8000/healthz > /dev/null; do sleep 1; done
	@echo "API is up at http://localhost:8000"

down:
	docker compose down

logs:
	docker compose logs -f api worker

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python scripts/seed_dev_data.py

test:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration

lint:
	uv run ruff check .
	uv run mypy app

fmt:
	uv run ruff format .
	uv run ruff check --fix .

eval:
	docker compose run --rm api python scripts/run_eval.py
