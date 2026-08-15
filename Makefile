.PHONY: install dev test lint format format-check typecheck package-check migration-check evidence-check docker-config docker-build docker-up docker-down demo migrate worker clean

install:
	python -m pip install -e ".[dev]"

dev:
	python src/workflow_engine/main.py

test:
	python -m pytest

lint:
	python -m ruff check src tests examples alembic scripts

format:
	python -m ruff format src tests examples alembic scripts

format-check:
	python -m ruff format --check src tests examples alembic scripts

typecheck:
	python -m pyright src/

package-check:
	python scripts/check_package.py

migration-check:
	python scripts/check_sqlite_migrations.py

evidence-check:
	python scripts/portfolio_demo.py
	python scripts/verify_portfolio_evidence.py artifacts/portfolio/async-workflow-engine-evidence

docker-config:
	docker compose config

docker-build:
	docker build --file frontend/Dockerfile frontend

docker-up:
	docker compose up -d

docker-down:
	docker compose down

migrate:
	alembic upgrade head

worker:
	celery -A workflow_engine.worker.celery_app worker --loglevel=info

demo:
	python examples/run_demo.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
