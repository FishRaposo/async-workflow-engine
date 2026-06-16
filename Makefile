.PHONY: install dev test lint format typecheck docker-up docker-down demo migrate worker clean

install:
	pip install -e ../shared-core[dev,docparse,embeddings]
	pip install -e ".[dev]"

dev:
	python src/workflow_engine/main.py

test:
	pytest

lint:
	ruff check src/workflow_engine tests examples alembic

format:
	ruff format src/workflow_engine tests examples alembic

typecheck:
	pyright src/

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
