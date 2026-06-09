# AGENTS.md — Async Workflow Engine

## What This Is

A declarative workflow orchestration engine that accepts YAML-defined DAGs, resolves step dependencies in topological order, dispatches tasks via a registry pattern, and tracks step-level status (`PENDING → RUNNING → COMPLETED/FAILED`). The API layer is FastAPI; the execution engine is an in-process `WorkflowExecutor` with deadlock detection. A Celery worker scaffold exists for future async dispatch.

## Commands

Run from within the `async-workflow-engine/` directory:

```bash
make install          # pip install -e ../shared-core && pip install -r requirements.txt
make dev              # python src/workflow_engine/main.py (starts uvicorn)
make test             # pytest (runs tests/test_core.py)
make lint             # ruff check .
make format           # ruff format .
make typecheck        # pyright src/
make docker-up        # docker compose up -d (PostgreSQL + Redis)
make docker-down      # docker compose down
make demo             # python examples/run_demo.py (runs lead_intake workflow)
make clean            # remove __pycache__, .pytest_cache, etc.
```

**Order matters:** `make docker-up` then `make install` before anything else.

## Entry Point

`src/workflow_engine/main.py` — Creates FastAPI app, instantiates `AppConfig`, `DatabaseManager`, `RedisManager`, registers the `BaseApplicationError` handler, and exposes two routes:

- `POST /workflows/run` — Accepts `WorkflowPayload.yaml_definition`, calls `load_workflow_yaml()` → `WorkflowExecutor.execute()`, returns step statuses
- `GET /health` — Probes PostgreSQL and Redis, returns per-dependency status

## Source Modules

| File | Purpose |
|------|---------|
| `src/workflow_engine/__init__.py` | Package marker |
| `src/workflow_engine/main.py` | FastAPI app, routes (`/workflows/run`, `/health`), dependency wiring |
| `src/workflow_engine/executor.py` | `WorkflowExecutor` class — DAG traversal, topological execution, deadlock detection, status tracking |
| `src/workflow_engine/parser.py` | `WorkflowConfig` and `StepConfig` Pydantic models, `load_workflow_yaml()` function using `yaml.safe_load` |
| `src/workflow_engine/tasks.py` | `TASK_REGISTRY` dict mapping task names to callables: `parse_text`, `classify_with_llm`, `send_notification` |
| `src/workflow_engine/storage.py` | `InMemoryWorkflowStorage` — stub dict-based persistence for run records |
| `src/workflow_engine/worker.py` | Celery app configured with Redis broker/backend, `sample_background_task` placeholder |
| `src/workflow_engine/config.py` | `AppConfig(BaseAppConfig)` — project-specific config, sets `APP_NAME = "async-workflow-engine"` |
| `src/workflow_engine/errors.py` | `application_error_handler` — global FastAPI handler for `BaseApplicationError` subclasses |

## Docker Services

From `docker-compose.yml`:

| Service | Image | Port | Container Name |
|---------|-------|------|----------------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | `template_postgres` |
| `redis` | `redis:7-alpine` | 6379 | `template_redis` |

Both have healthchecks configured. Volumes: `pgdata`, `redisdata`.

## Layout

```
async-workflow-engine/
├── src/workflow_engine/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + routes
│   ├── executor.py           # WorkflowExecutor (DAG engine)
│   ├── parser.py             # YAML → WorkflowConfig/StepConfig
│   ├── tasks.py              # TASK_REGISTRY + task functions
│   ├── storage.py            # InMemoryWorkflowStorage stub
│   ├── worker.py             # Celery app + sample task
│   ├── config.py             # AppConfig extends BaseAppConfig
│   └── errors.py             # Error handler for BaseApplicationError
├── tests/
│   └── test_core.py          # Health endpoint test
├── examples/
│   ├── run_demo.py           # Standalone DAG execution demo
│   └── sample_workflow.yaml  # lead_intake workflow definition
├── docs/
│   ├── architecture.md
│   ├── design-decisions.md
│   ├── failure-modes.md
│   ├── roadmap.md
│   └── security.md
├── .env.example
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── requirements.txt
├── pyrightconfig.json
├── ruff.toml
└── pytest.ini
```

## Current State

**Functional MVP.** The core execution path works end-to-end:

- ✅ YAML parsing with Pydantic validation (`WorkflowConfig`, `StepConfig`)
- ✅ DAG execution with topological dependency resolution
- ✅ Deadlock detection (breaks loop when no step can execute)
- ✅ Task registry dispatch (`TASK_REGISTRY` → callable lookup)
- ✅ Step status tracking (`PENDING → RUNNING → COMPLETED/FAILED`)
- ✅ FastAPI endpoint accepts YAML and returns step statuses
- ✅ Health check probes PostgreSQL and Redis
- ✅ Celery worker configured (not yet wired to executor)
- ⚠️ Storage is in-memory stub (not persisting to PostgreSQL)
- ⚠️ Retry field is parsed but not enforced
- ⚠️ No step I/O piping (tasks take no arguments)
- ⚠️ Docker container names still use `template_` prefix

## Key Dependencies

Beyond shared-core (`config`, `database`, `redis`, `logging`, `errors`):

| Package | Version | Used For |
|---------|---------|----------|
| `pyyaml` | ≥6.0 | Workflow definition parsing (`yaml.safe_load`) |
| `celery` | ≥5.3 | Background task worker (scaffold, not yet integrated) |
| `loguru` | ≥0.7 | Structured logging in executor and tasks |
| `sqlalchemy` | ≥2.0 | Database health check, future persistence |
| `httpx` | ≥0.24 | HTTP client (available, not yet used) |

## When to Update This File

- When adding new modules to `src/workflow_engine/` (especially new task types or storage backends)
- When wiring Celery worker to the executor (changes execution model)
- When adding new API endpoints (e.g., `/workflows/{id}/status`, `/workflows/{id}/rerun`)
- When replacing `InMemoryWorkflowStorage` with PostgreSQL persistence
- When implementing retry logic (changes `StepConfig` behavior)
- When adding new Docker services (e.g., Flower for Celery monitoring)
- When renaming Docker container names from `template_` prefix
- When adding webhook or schedule trigger endpoints
