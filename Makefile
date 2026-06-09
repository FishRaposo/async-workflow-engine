.PHONY: install dev test lint format typecheck docker-up docker-down demo clean

install:
	pip install -e ../shared-core
	pip install -r requirements.txt

dev:
	python src/workflow_engine/main.py

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	pyright src/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

demo:
	python examples/run_demo.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
