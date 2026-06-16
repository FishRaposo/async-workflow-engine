# Execution Plan — Async Workflow Engine

This document records what was built to bring the engine from a ~75% scaffold to
a fully-implemented, tested, documented MVP, and what remains.

## Starting State (scaffold)

- Working in-process DAG executor with deadlock detection and a retry loop.
- YAML parser with Pydantic models and cycle detection.
- A task registry of three placeholder tasks returning constant strings.
- `InMemoryWorkflowStorage` (not wired) and a `DatabaseWorkflowStorage` skeleton.
- A Celery app with a `sample_background_task(x, y)` placeholder, not wired.
- Two endpoints (`/workflows/run`, `/health`) plus a handful of tests.
- Alembic scaffold (`env.py`, `alembic.ini`) with no migrations.

## What Was Built

### Core engine

- **Conditional branching** — `StepCondition` (`equals`/`contains`/`not_equals`)
  on `StepConfig`; the executor evaluates it against prior results and marks
  non-matching steps `SKIPPED` (resolved, so downstream steps don't deadlock).
  Condition source steps are treated as implicit dependencies for ordering.
- **Step parameters** — `params` on each step, forwarded to tasks as `params=`.
- **Retry + backoff** — exponential backoff capped at `max_backoff`, injectable
  `sleep_fn` so tests run instantly.
- **Dead-letter queue** — every step that exhausts retries is appended to
  `executor.dead_letters` with task, error, attempts, and params.
- **Persistence hook** — `on_step` callback fires after each step resolves.
- **`overall_status`** — aggregates per-step statuses to `completed`/`failed`/`partial`.

### Real tasks (offline-first, real-when-keyed)

- `parse_text` — real text stats via `shared_core.docparse.chunk_text`.
- `classify_with_llm` — mirrors the llm-cost-latency-monitor SDK pattern:
  `mocked_response` short-circuit → real `LLMClientFactory` call when a key is
  set → deterministic offline simulation. ImportError/no-key fall through cleanly.
- `send_notification` — side-effect-free simulated dispatcher.
- `always_fail` — exercises retries/DLQ.

### Persistence (DB default, in-memory fallback)

- `db.py` — `probe_database()` (`SELECT 1` + `create_tables`) caches `db_available`;
  `get_storage()` returns `DatabaseWorkflowStorage` when reachable, else in-memory.
  Mirrors the migrated-services `db_available` pattern.
- `storage_db.py` rewritten to the richer interface (status, errors, dead_letters,
  task_names, run_id reuse for rerun) backed by SQLAlchemy; rerun overwrites
  cleanly (delete-then-insert, no orphan steps).
- `models.py` — added a `dead_letters` JSON column to `WorkflowRun`.
- **Alembic** — `0001_initial_schema.py` creates both tables (validated against
  SQLite with `render_as_batch=True`).

### Background dispatch

- `worker.py` — `run_workflow_task` runs a full workflow (probe → storage →
  runner) in a Celery task; importable with no broker. `run_due_schedules` hook.

### Scheduling & triggers

- `scheduler.py` — croniter-backed `WorkflowScheduler` (register/due/mark_ran),
  pure and clock-injectable.
- `webhooks.py` — in-memory `WebhookRegistry`.
- `dag.py` — `build_dag()` `{nodes, edges, status}` projection for a UI.
- `runner.py` — single `run_workflow()` shared by API and worker.

### API

New/rounded-out endpoints: `POST /workflows/run` (sync/async), `POST
/workflows/{id}/rerun`, `GET /workflows`, `GET /workflows/{run_id}`, `GET
/workflows/{run_id}/dag`, `GET /workflows/dead-letters`, webhook register/list/fire,
schedule create/list/delete/run-due, `GET /tasks`, and `GET /health` (now reports
the active storage backend). Storage resolves per request via the probe; startup
runs the probe in a FastAPI lifespan handler.

### Tests

Expanded from ~6 to a full suite: parser, executor, tasks, scheduler, webhooks,
dag, runner (in-memory **and** SQLite via `MockDatabase`), both storage backends,
DB probe, Celery worker (eager), every API endpoint (success + error), models,
and a demo smoke test. No network, DB, or broker required.

### Docs & spine

README rewritten to the full standard with a Mermaid architecture diagram;
architecture/design-decisions/failure-modes/roadmap/security expanded; AGENTS.md
updated; `croniter` + `alembic` + `psycopg` added to requirements/pyproject;
Makefile gains a `migrate` target.

## What's Next

1. Parallel execution of independent steps within a run (thread/async pool).
2. Celery-beat integration so schedules fire without a manual tick.
3. Persist schedule/webhook registries (survive restart).
4. Typed step-I/O contract for piping structured data between steps.
5. AuthN/AuthZ on the API and per-workflow RBAC.
6. OpenTelemetry spans from trigger → run → step (shared_core.tracing).
