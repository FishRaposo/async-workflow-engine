# AGENTS.md — Async Workflow Engine

## What This Is

A declarative workflow orchestration engine. It accepts YAML-defined DAGs,
resolves step dependencies in topological order, dispatches tasks via a registry,
and tracks step-level status (`PENDING → RUNNING → COMPLETED/FAILED/SKIPPED`).
It supports retries with backoff, conditional branching, a dead-letter queue,
cron scheduling, webhook triggers, manual rerun, and real background dispatch via
Celery. Runs persist to PostgreSQL by default with a transparent in-memory
fallback. The HTTP surface is FastAPI; the engine is offline-first (no API keys,
no DB, no broker required).

## Commands

Run from within `async-workflow-engine/` (use the venv's python):

```bash
make install          # python -m pip install -e ".[dev]"
make dev              # uvicorn (src/workflow_engine/main.py:main)
make test             # pytest (203 tests, no network/DB/broker needed)
make lint             # ruff check src/workflow_engine tests examples alembic
make format           # ruff format ...
make typecheck        # pyright src/
make migrate          # alembic upgrade head
make worker           # celery -A workflow_engine.worker.celery_app worker
make docker-up        # docker compose up -d (PostgreSQL + Redis)
make docker-down      # docker compose down
make demo             # python examples/run_demo.py
make clean            # remove caches
```

## Entry Point

`src/workflow_engine/main.py` — FastAPI app. A lifespan handler probes the DB at
startup (`probe_database`) to select the storage backend. Routes:

| Method & Path | Handler |
|---------------|---------|
| `POST /workflows/validate` | `validate_workflow` |
| `POST /workflows/run` | `run_workflow_endpoint` (sync, or async via `async_dispatch`) |
| `POST /workflows/{run_id}/rerun` | `rerun_workflow` |
| `GET /workflows` | `list_workflows` |
| `GET /workflows/dead-letters` | `list_dead_letters` (declared before `{run_id}`) |
| `GET /workflows/{run_id}` | `get_workflow_run` |
| `GET /workflows/{run_id}/dag` | `get_workflow_dag` |
| `POST /webhooks/{name}/register` | `register_webhook` |
| `GET /webhooks` | `list_webhooks` |
| `POST /webhooks/{name}` | `trigger_webhook` |
| `POST /schedules` | `create_schedule` |
| `GET /schedules` | `list_schedules` |
| `DELETE /schedules/{name}` | `delete_schedule` |
| `POST /schedules/run-due` | `run_due_schedules` |
| `GET /tasks` | `list_tasks` |
| `GET /health` | `health_check` (adds `storage` = database/in-memory) |

## Source Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, all routes, dispatch (sync/Celery), storage selection |
| `runner.py` | `run_workflow()` — parse → execute → persist; shared by API + worker |
| `executor.py` | `WorkflowExecutor` — DAG traversal, retries, branching, DLQ, `on_step` hook |
| `contracts.py` | Workflow-owned storage/task/idempotency compatibility contracts with in-memory defaults |
| `trace.py` | `TraceContext` and deterministic in-process execution events |
| `locks.py` | In-memory lock provider and caller-supplied Redis lock adapter |
| `auth.py` | Disabled-by-default local API-key role policy and rate-limiter primitives |
| `versions.py` | Deterministic YAML content hashes and in-memory workflow version store |
| `parser.py` | `WorkflowConfig`/`StepConfig`/`StepCondition`, `load_workflow_yaml`, cycle detection |
| `tasks.py` | `TASK_REGISTRY`: `parse_text` (docparse), `classify_with_llm` (sim/real LLM), `send_notification`, `always_fail` |
| `scheduler.py` | `WorkflowScheduler` (croniter): register/due/mark_ran |
| `webhooks.py` | `WebhookRegistry` — name → workflow YAML |
| `dag.py` | `build_dag()` — `{nodes, edges, status}` projection for a UI |
| `db.py` | `probe_database()` / `get_storage()` — DB-default, in-memory fallback |
| `storage.py` | `InMemoryWorkflowStorage` (no-DB fallback) |
| `storage_db.py` | `DatabaseWorkflowStorage` (SQLAlchemy, default) |
| `models.py` | `WorkflowRun` (+ `dead_letters` JSON), `StepExecution` |
| `worker.py` | Celery app + `run_workflow_task`, `run_due_schedules` (importable w/o broker) |
| `runtime.py` | Shared offline/durable schedule, webhook, version, idempotency, and event adapters |
| `trace_store.py` | In-memory execution-event adapter and API event serialization |
| `config.py` | `AppConfig(BaseAppConfig)` |
| `errors.py` | Re-exports `application_error_handler` |
| `internal/vendor_core/` | Package-private v1.3.0 infrastructure import closure; see `THIRD_PARTY_NOTICES.md` |

`alembic/versions/0001_initial_schema.py` creates run/step tables;
`0002_runtime_persistence.py` adds pinned definitions, schedules, webhooks,
idempotency records, and execution events.

## Key Behaviors / Gotchas

- **Storage selection**: `db.db_available` is a module-level cache set by
  `probe_database()`. `get_storage()` reads it and keeps one process-local
  in-memory fallback, so `main._storage()` can resolve per request without
  losing offline runs. The probe uses a 2s connect timeout so it fails fast.
- **Route order**: `/workflows/dead-letters` MUST stay declared before
  `/workflows/{run_id}` or it gets captured as a run id.
- **Async dispatch**: only when `async_dispatch=true` on the request or
  `WORKFLOW_ASYNC=1`; requires a live Celery worker + Redis. Default is sync.
- **Configured concurrency**: `WORKFLOW_CONCURRENCY_LIMIT` reaches synchronous
  API runs, async Celery dispatch, direct worker execution, and due-schedule
  execution. The default `1` retains legacy YAML-order execution.
- **Configured local rate limits**: recognized API keys use key buckets; unknown
  or absent keys use client identity. Bucket mutation is process-local and
  lock-protected; the feature remains off at the default limit `0`.
- **LLM**: `classify_with_llm` is mock → real (`LLMClientFactory`, needs a key) →
  deterministic simulation. Offline by default.
- **Conditional branching**: a condition's source step is an implicit dependency;
  non-matching steps are `SKIPPED` (resolved, so downstream steps don't deadlock).
- **Task 2 core behavior**: concurrency is opt-in only (`concurrency_limit > 1`);
  omitted or `1` preserves synchronous YAML-order execution. The contracts,
  trace, locks, auth/rate-limit primitives, version store, and in-memory
  schedule/webhook adapters are direct interfaces only. **Task 3 owns FastAPI
  route wiring and database persistence/migrations for those capabilities.**
- **Task 3 runtime integration**: normal API/worker runs store deterministic
  version hashes and ordered traces; reruns use the recorded version when present.
  Schedule/webhook registries are shared in memory offline and use SQLAlchemy
  adapters after the database probe. HMAC secrets, idempotency headers, API-key
  roles, rate limits, and execution locks are disabled unless configured. Redis
  locks are opt-in through `WORKFLOW_REDIS_LOCKING_ENABLED`; Redis remains
  optional and the in-memory lock stays the default.

## Docker Services (`docker-compose.yml`)

| Service | Image | Port | Container |
|---------|-------|------|-----------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | `awfe_postgres` |
| `redis` | `redis:7-alpine` | 6379 | `awfe_redis` |

## Tests

`tests/` — parser, executor, tasks, scheduler, webhooks, dag, runner (in-memory +
SQLite via the vendored `MockDatabase`), both storage backends, db probe,
Celery worker (eager, no broker), every API endpoint (success + error), models,
an Alembic SQLite upgrade, runtime persistence, opt-in security controls, and a demo
smoke test. 203 tests, all offline. The dashboard separately has 25 Vitest tests and
6 Chromium smoke checks; Docker local verification is optional and CI-configured.

## When to Update This File

- New `src/workflow_engine/` modules, task types, or storage backends.
- New API endpoints or changes to dispatch/storage selection.
- New Celery tasks or scheduler/beat wiring.
- New alembic migrations or model columns.
- New Docker services (e.g. Flower for Celery monitoring).
