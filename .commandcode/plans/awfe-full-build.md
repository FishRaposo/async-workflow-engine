# Implementation Plan: async-workflow-engine Full Build

## Current State

Functional DAG executor (YAML → Pydantic → topological execution → status map), FastAPI endpoints, Celery scaffold, Docker Compose, documentation. 1 test.

## Gap Summary

| Category | Count | Items |
|----------|-------|-------|
| Critical fixes | 5 | psycopg driver, docker names, pyproject.toml, storage timestamp, worker config import |
| Core features | 4 | Retry logic, step I/O piping, pre-execution validation, cycle detection at parse time |
| Persistence | 3 | PostgreSQL models + migrations + wired storage |
| Async dispatch | 3 | Celery async execution, /workflows/{run_id}/status, /workflows/validate |
| Testing | 15+ | Parser, executor (linear/fan-out/diamond/cycle), retry, registry miss, status transitions, API endpoints |

---

## Wave 1: Critical Fixes (5 items)

### 1A. Add `psycopg[binary]` to requirements.txt + pyproject.toml
### 1B. Fix docker-compose container names (`template_*` → `awfe_*`)
### 1C. Fix pyproject.toml — description, add missing deps (pyyaml, loguru, sqlalchemy, redis, celery, httpx)
### 1D. Fix `storage.py` — use `datetime.now().isoformat()` instead of hardcoded string
### 1E. Fix `worker.py` — import `AppConfig` instead of `BaseAppConfig`, use `create_celery_app` from shared-core

---

## Wave 2: Core Engine Features

### 2A. Retry logic in `executor.py` — honor `StepConfig.retries` with configurable backoff
### 2B. Step I/O piping — pass `results` dict to task functions as kwargs `(context={step_id: result})`
### 2C. Pre-execution validation — validate all task registry references before first step runs
### 2D. Cycle detection at parse time — Kahn's algorithm in `parser.py`, raises `WorkflowValidationError`

---

## Wave 3: PostgreSQL Persistence

### 3A. Create SQLAlchemy models — `WorkflowRun`, `StepExecution` in `models.py`
### 3B. Replace `InMemoryWorkflowStorage` with `DatabaseWorkflowStorage` using `DatabaseManager`
### 3C. Initialize Alembic migrations for the project
### 3D. Wire storage into `main.py` — persist runs on workflow execution

---

## Wave 4: Async Celery Dispatch

### 4A. Rewrite `POST /workflows/run` — enqueue task, return `run_id` immediately
### 4B. Create Celery task `execute_workflow_run` in `worker.py` that runs executor + persists results
### 4C. Add `GET /workflows/{run_id}/status` endpoint
### 4D. Add `GET /workflows/{run_id}` endpoint (full details)
### 4E. Add `POST /workflows/validate` endpoint (dry-run without execution)
### 4F. Add `GET /tasks` endpoint (list available tasks from registry)

---

## Wave 5: Comprehensive Tests

### 5A. Parser tests (valid YAML, invalid YAML, malformed schema, cycle detection)
### 5B. Executor tests (linear, fan-out, diamond, single-step, empty, retry, registry miss)
### 5C. API endpoint tests (run, validate, health, tasks, status)
### 5D. Storage tests (save, retrieve, update status)
### 5E. conftest.py with TestClient, MockDatabase, MockRedisClient fixtures

---

## Wave 6: Documentation + Polish

### 6A. Update README — remove "Known Limitations" items that are now fixed, add new endpoints
### 6B. Update implementation_plan.md — check off milestones
### 6C. Update architecture.md — add PostgreSQL models, async dispatch flow
### 6D. Bump version to 1.0.0

---

## Files to Create (New)

| File | Wave |
|------|------|
| `src/workflow_engine/models.py` | 3 |
| `src/workflow_engine/storage_db.py` | 3 |
| `alembic.ini` | 3 |
| `alembic/env.py` | 3 |
| `alembic/versions/` | 3 |
| `tests/conftest.py` | 5 |
| `tests/test_parser.py` | 5 |
| `tests/test_executor.py` | 5 |
| `tests/test_api.py` | 5 |
| `tests/test_storage.py` | 5 |

## Files to Modify (Existing)

| File | Wave | Changes |
|------|------|---------|
| `requirements.txt` | 1 | Add `psycopg[binary]`, `alembic` |
| `pyproject.toml` | 1 | Fix description, add all deps |
| `docker-compose.yml` | 1 | Fix container names |
| `src/workflow_engine/storage.py` | 1+3 | Fix timestamp, then rewrite as DB-backed |
| `src/workflow_engine/worker.py` | 1+4 | Fix config import, add execute_workflow_run task |
| `src/workflow_engine/executor.py` | 2 | Retry logic, step I/O piping, pre-validation |
| `src/workflow_engine/parser.py` | 2 | Cycle detection at parse time |
| `src/workflow_engine/tasks.py` | 2 | Update task signatures to accept context |
| `src/workflow_engine/main.py` | 3+4 | Wire storage, async dispatch, new endpoints |
| `docs/implementation_plan.md` | 6 | Check off milestones |
| `docs/architecture.md` | 6 | Add new modules and flows |
| `README.md` | 6 | Update known limitations, endpoints |

## Verification

After each wave: `make lint && make test`
After full build: `make demo && make typecheck`
