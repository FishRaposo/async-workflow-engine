# Async Workflow Engine

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: MVP](https://img.shields.io/badge/status-MVP-yellow)

**A declarative workflow orchestration engine that parses YAML DAGs, runs steps in topological order with retries and conditional branching, dispatches runs to Celery workers, and persists every run to PostgreSQL — with a full offline fallback.**

## Why This Exists

Backend systems constantly coordinate multi-step processes — data ingestion, lead intake, notification chains — where steps depend on each other, some steps should only run under certain conditions, and failures must be quarantined rather than lost. Off-the-shelf orchestrators (Airflow, Prefect, Temporal) are powerful but heavyweight, and they hide the mechanics of DAG resolution, retries, scheduling, and dead-lettering behind a framework.

This project builds those mechanics from first principles: topological dependency resolution, a step state machine, retry-with-backoff, conditional branching, cron scheduling, webhook triggers, a dead-letter queue, and background dispatch via Celery — all wired through a FastAPI surface that exposes everything a dashboard needs.

It is **offline-first**: it runs and tests with no API keys, no database, and no message broker, using deterministic simulations. When a PostgreSQL DB, a Redis broker, or an LLM API key *is* present, the real paths light up automatically.

## What It Demonstrates

- **DAG execution engine** — `WorkflowExecutor` resolves dependencies in topological order with deadlock detection, retry-with-exponential-backoff, and a per-step persistence hook.
- **Conditional branching** — a step runs only when a prior step's result satisfies a declared condition (`equals` / `contains` / `not_equals`); otherwise it is `SKIPPED` without deadlocking downstream steps.
- **Dead-letter queue** — every step that exhausts its retries is quarantined with its error, attempts, and params for inspection and rerun.
- **PostgreSQL persistence by default, in-memory fallback** — a startup DB probe selects `DatabaseWorkflowStorage`; if no DB is reachable it transparently falls back to `InMemoryWorkflowStorage`, so tests and the demo need no database. Alembic migrations ship for both tables.
- **Real Celery dispatch** — `run_workflow_task` runs a full workflow in the background via `shared_core.tasks.create_celery_app`, importable with no broker running.
- **Cron scheduling** — `WorkflowScheduler` (croniter-backed) registers workflows on a cron expression and computes which are due.
- **Webhook triggers** — register a workflow under a name and fire it with `POST /webhooks/{name}`.
- **Real task implementations** — `parse_text` (via `shared_core.docparse`), `classify_with_llm` (mock → real LLM via `shared_core.llm.LLMClientFactory` → deterministic simulation), and `send_notification`.
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
| **Migrations** | Alembic 1.13+ | Versioned schema for `workflow_runs`, `step_executions` |
| **Cache/Broker** | Redis 7 | Celery broker + health check target |
| **ORM** | SQLAlchemy 2.0+ | Persistence + connection pooling |
| **Logging** | Loguru 0.7+ | Structured, step-level execution tracing |
| **Shared Library** | `shared-core` v1.3.0 | config, database, redis, logging, errors, health, tasks, llm, docparse |

## Local Setup

```bash
cd async-workflow-engine

# 1. Create a venv and install (installs shared-core first)
python -m venv .venv
.venv/Scripts/python -m pip install -e ../shared-core[dev,docparse,embeddings]
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
| Background dispatch | `make docker-up`, run a Celery worker, send `async_dispatch=true` or set `WORKFLOW_ASYNC=1` |
| Real LLM classification | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` |

Everything works with **none** of these set — the engine falls back to in-memory storage, synchronous dispatch, and deterministic classification.

## Demo

```bash
make demo            # python examples/run_demo.py
```

The demo runs five scenarios fully offline and asserts each: (1) a conditional-branching `lead_intake` workflow, (2) the DAG projection a dashboard would render, (3) a failing step landing in the dead-letter queue, (4) persistence + manual rerun against the in-memory fallback, and (5) cron scheduling. It exits 0.

## Tests

```bash
make test            # pytest
```

Coverage spans every core module — parser (validation, conditions, cycles), executor (linear/fan-out/diamond DAGs, retries, branching, DLQ, hooks), scheduler, webhooks, DAG projection, runner (end-to-end against in-memory **and** SQLite stores via `shared_core.testing.MockDatabase`), both storage backends, the DB probe, the Celery worker (eager, no broker), every API endpoint (success + error paths), and a smoke test that the demo runs. No test needs a network, a real database, or a broker.

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
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | _(unset)_ | Enable real LLM classification |
| `LOG_LEVEL` | `INFO` | Loguru verbosity |

## Known Limitations

1. **Scheduler is tick-driven, not a daemon** — `WorkflowScheduler` computes due runs; firing them requires a Celery-beat loop or a periodic `POST /schedules/run-due`. The state is in-memory.
2. **Webhook/schedule registries are in-memory** — registered triggers and schedules are lost on restart (runs themselves persist to PostgreSQL).
3. **No authentication** on API endpoints (development posture).
4. **Sequential step execution** — independent steps run in dependency order but not in parallel within a single run.
5. **Async dispatch needs a live broker** — `async_dispatch=true` requires a running Celery worker + Redis; otherwise use the default synchronous path.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md). Highlights: parallel fan-out execution, Celery-beat-driven scheduling, persistent schedule/webhook registries, workflow versioning, OpenTelemetry tracing, and a step-I/O contract for typed piping between steps.

## Related Projects

A **Wave 1** project in the AI Infrastructure Showcase Portfolio. It shares `shared-core` (config, database, redis, logging, errors, health, tasks, llm, docparse) with the rest of the portfolio and provides orchestration patterns reused by the agent and document-pipeline projects.
