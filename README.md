# Async Workflow Engine

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: MVP](https://img.shields.io/badge/status-MVP-yellow)

**DAG-based async workflow orchestrator with Celery, dependency resolution, retry logic, and a YAML workflow DSL.**

## Why This Exists

Backend systems constantly coordinate multi-step processes — data ingestion, lead intake, notification chains — where steps depend on each other, some steps should only run under certain conditions, and failures must be quarantined rather than lost. Off-the-shelf orchestrators (Airflow, Prefect, Temporal) are powerful but heavyweight, and they hide the mechanics of DAG resolution, retries, scheduling, and dead-lettering behind a framework.

This project builds those mechanics from first principles: topological dependency resolution, a step state machine, retry-with-backoff, conditional branching, cron scheduling, webhook triggers, a dead-letter queue, and background dispatch via Celery — all wired through a FastAPI surface that exposes everything a dashboard needs.

It is **offline-first**: it runs and tests with no API keys, no database, and no message broker, using deterministic simulations. When a PostgreSQL DB, a Redis broker, or an LLM API key with the `llm` extra *is* present, the real paths light up automatically.

## What It Demonstrates

- **DAG execution engine** — `WorkflowExecutor` resolves dependencies in topological order with deadlock detection, retry-with-exponential-backoff, and a per-step persistence hook.
- **Conditional branching** — a step runs only when a prior step's result satisfies a declared condition (`equals` / `contains` / `not_equals`); otherwise it is `SKIPPED` without deadlocking downstream steps.
- **Dead-letter queue** — every step that exhausts its retries is quarantined with its error, attempts, and params for inspection and rerun.
- **Optional durable runtime** — a startup DB probe selects SQLAlchemy-backed runs, schedules, webhooks, version records, idempotency claims, and execution events when PostgreSQL is reachable. Otherwise the same features use process-local in-memory adapters, so tests and the demo need no database.
- **Real Celery dispatch** — `run_workflow_task` runs a full workflow in the background via the vendored `create_celery_app`, importable with no broker running.
- **Cron scheduling** — `WorkflowScheduler` (croniter-backed) registers workflows on a cron expression and computes which are due.
- **Webhook triggers** — register a workflow under a name and fire it with `POST /webhooks/{name}`; an HMAC signature is enforced when a secret was registered.
- **Deliberate opt-ins** — local API-key roles, local rate limiting, execution locks, Redis-backed locks, concurrency, and Celery beat are disabled unless configured; the offline default remains synchronous and broker-free.
- **Definition-level typed I/O** — set root-level `typed_io: true` to pass `TaskInput` into typed task objects and require a `TaskResult` response through sync API, Celery worker, and due-schedule execution. Omitting it preserves the established keyword-callable/dictionary behavior; an invalid typed result follows normal retry and DLQ handling.
- **Real task implementations** — `parse_text` (via the vendored document chunker), `classify_with_llm` (mock → real LLM via the vendored `LLMClientFactory` → deterministic simulation), and `send_notification`.
- **Dashboard-ready API** — run/rerun/list/inspect runs, a `{nodes, edges, status}` DAG projection, schedules, webhooks, and the dead-letter queue.

## Architecture

```mermaid
graph TB
    Client["HTTP Client / Dashboard"]
    Webhook["External Event"]
    Cron["Cron Tick"]

    Client -->|"POST /workflows/run"| API["FastAPI App<br/>main.py"]
    Webhook -->|"POST /webhooks/{name}"| API
    Cron -->|"POST /schedules/run-due"| API

    API --> Parser["YAML Parser<br/>parser.py"]
    Parser -->|WorkflowConfig| Runner["Runner<br/>runner.py"]
    Runner --> Executor["WorkflowExecutor<br/>executor.py"]
    Executor -->|task lookup| Registry["TASK_REGISTRY<br/>tasks.py"]
    Executor -->|failed steps| DLQ["Dead-Letter Queue"]

    API -->|"async_dispatch=true"| Celery["Celery Worker<br/>worker.py"]
    Celery --> Runner

    Runner -->|persist| Storage{"db_available?"}
    Storage -->|yes| DBStore["DatabaseWorkflowStorage<br/>storage_db.py"]
    Storage -->|no| MemStore["InMemoryWorkflowStorage<br/>storage.py"]
    DBStore --> PG["PostgreSQL<br/>pgvector:pg16"]
    Celery -->|broker| Redis["Redis 7"]

    style API fill:#009688,color:#fff
    style Executor fill:#1565c0,color:#fff
    style Parser fill:#7b1fa2,color:#fff
    style Registry fill:#e65100,color:#fff
    style Celery fill:#37474f,color:#fff
```

See [docs/architecture.md](docs/architecture.md) for sequence and state diagrams.

## Tech Stack

| Component | Choice | Justification |
|-----------|--------|---------------|
| **API Framework** | FastAPI 0.100+ | Async-ready, auto OpenAPI docs, Pydantic integration |
| **YAML Parsing** | PyYAML 6.0+ | `yaml.safe_load` prevents code execution |
| **Validation** | Pydantic v2 | Schema enforcement for workflow/step config and conditions |
| **Task Queue** | Celery 5.3+ | Background workflow dispatch with Redis broker |
| **Scheduling** | croniter 2.0+ | Real cron-expression parsing for scheduled workflows |
| **Database** | PostgreSQL 16 (pgvector) | Run/step persistence; portfolio-shared image |
| **Migrations** | Alembic 1.13+ | Versioned schema for runs, steps, runtime stores, idempotency, and execution events |
| **Cache/Broker** | Redis 7 | Celery broker + health check target |
| **ORM** | SQLAlchemy 2.0+ | Persistence + connection pooling |
| **Logging** | Loguru 0.7+ | Structured, step-level execution tracing |
| **Vendored runtime** | archived v1.3.0 import closure | config, database, redis, logging, errors, health, tasks, llm, docparse |

## Local Setup

```bash
cd async-workflow-engine

# 1. Create a venv and install the self-contained package
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"

# 2. (Optional) start infrastructure for the DB/broker paths
make docker-up          # PostgreSQL + Redis
cp .env.example .env

# 3. Run the API
make dev                # uvicorn on :8000

# 4. Run the demo (no DB / keys / broker needed)
make demo
```

### Optional real-path activation

| Want | Set |
|------|-----|
| Persist runs to PostgreSQL | `DATABASE_URL` reachable + run `alembic upgrade head` |
| Background dispatch | Start PostgreSQL/Redis, run a Celery worker, then send `async_dispatch=true` or set `WORKFLOW_ASYNC=1` |
| Real LLM classification | `python -m pip install -e ".[dev,llm]"` + `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` |
| PDF, DOCX, or HTML document parsing | `python -m pip install -e ".[document-parsers]"` |

Everything works with **none** of these set — the engine falls back to in-memory
storage, synchronous dispatch, and deterministic classification. Deterministic
plain-text chunking is always part of the base runtime; only heavyweight document
formats and hosted LLM providers are optional.

## Demo

```bash
make demo            # python examples/run_demo.py
```

The demo runs five scenarios fully offline and asserts each: (1) a conditional-branching `lead_intake` workflow, (2) the DAG projection a dashboard would render, (3) a failing step landing in the dead-letter queue, (4) persistence + manual rerun against the in-memory fallback, and (5) cron scheduling. It exits 0.

## Tests

```bash
make test            # pytest
```

The verified Python suite has **206 tests**. It covers parser validation, dependency resolution, retries, branching, DLQ, runtime persistence, versioning, idempotency, optional security controls, migrations, the Celery worker in eager mode, and every API endpoint. The dashboard has **25 Vitest tests** and **6 Chromium smoke checks**. These automated checks run without a live PostgreSQL, Redis, Celery worker, or hosted LLM.

The finalization evidence is reproducible by `make evidence-check`; the normalized evidence hash is `7a2584c22d4d91fbf9368194d068e94ced6dd149f87aa72e46f88f4dc4581029`. Wheel installation/import, SQLite migrations, and forbidden-dependency scans are separate green CI gates. Docker was not available on the finalization machine; Compose configuration and the frontend container build remain CI gates, not locally verified infrastructure.

## API Reference

| Method & Path | Purpose |
|---------------|---------|
| `POST /workflows/validate` | Validate a YAML definition (schema + registry + cycles) |
| `POST /workflows/run` | Run a workflow (sync, or async via `async_dispatch`/`WORKFLOW_ASYNC`) |
| `POST /workflows/{run_id}/rerun` | Re-run a stored workflow under the same run id |
| `GET /workflows` | List recent runs |
| `GET /workflows/{run_id}` | Full run record (statuses, results, errors, dead letters) |
| `GET /workflows/{run_id}/dag` | `{nodes, edges, status}` projection for a UI |
| `GET /workflows/dead-letters` | Dead-letter queue (all, or `?run_id=`) |
| `POST /webhooks/{name}/register` | Register a workflow under a webhook name |
| `GET /webhooks` | List registered webhook triggers |
| `POST /webhooks/{name}` | Fire the workflow bound to a webhook |
| `POST /schedules` | Register a cron-scheduled workflow |
| `GET /schedules` | List schedules (with next-run times) |
| `DELETE /schedules/{name}` | Remove a schedule |
| `POST /schedules/run-due` | Manually fire any due schedules |
| `GET /tasks` | List registered task functions |
| `GET /health` | DB + Redis health and active storage backend |

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_NAME` | `async-workflow-engine` | Service identifier |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/postgres` | Persistence target (probed at startup) |
| `REDIS_URL` | `redis://localhost:6379/0` | Health + Celery broker |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Background dispatch |
| `WORKFLOW_ASYNC` | _(unset)_ | `1`/`true` to route runs through Celery by default |
| `WORKFLOW_AUTH_REQUIRED` | `false` | Require `X-API-Key` values from `WORKFLOW_API_KEYS` (`key:viewer|operator|admin`) |
| `WORKFLOW_RATE_LIMIT` | `0` | Enable the process-local rate limiter; `0` leaves it disabled |
| `WORKFLOW_LOCKING_ENABLED` | `false` | Reject duplicate synchronous workflow execution by canonical YAML hash |
| `WORKFLOW_REDIS_LOCKING_ENABLED` | `false` | Use Redis locks when locking is enabled and Redis is available |
| `WORKFLOW_CONCURRENCY_LIMIT` | `1` | Opt in to parallel execution of independent ready steps |
| `WORKFLOW_CELERY_BEAT` | `false` | Enable the Celery-beat schedule hook |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | _(unset)_ | Enable real LLM classification |
| `LOG_LEVEL` | `INFO` | Loguru verbosity |

## Known Limitations

1. **Scheduler is tick-driven by default** — the API can dispatch due schedules, and the Celery-beat hook is opt-in; no live worker/broker deployment was exercised in finalization.
2. **Offline runtime state is process-local** — schedules, webhooks, versions, idempotency claims, and execution events become durable only after the PostgreSQL probe succeeds.
3. **Security controls are local, opt-in primitives** — API-key roles, rate limits, locks, and webhook HMAC are implemented but require deliberate configuration and production-grade key/network/observability operations.
4. **Async dispatch needs a live broker** — `async_dispatch=true` requires a running Celery worker + Redis; otherwise use the default synchronous path.
5. **Frontend deployment is deferred** — the production image excludes development dependencies, but the 2026-08-15 `npm audit --omit=dev` still reports 3 high findings in the locked Next.js 14 production tree. The offline dashboard is not presented as a production-hardened hosted service.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for deliberately deferred product work. The repository does not claim a live production PostgreSQL/Redis/Celery deployment or a hosted-LLM integration.

## Related Projects

The package vendors its required infrastructure import closure under `workflow_engine.internal.vendor_core`; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Packaging is self-contained: the verified wheel has no sibling-repository or Git-URL runtime dependency.
