# Project Roadmap — Async Workflow Engine

Milestones for the engine. Items marked ✅ are implemented in this MVP.

---

## Milestone 1: Core DAG Engine ✅ (Completed)

- ✅ Declarative YAML parser with Pydantic validation (`WorkflowConfig`, `StepConfig`, `StepCondition`).
- ✅ In-process topological executor with parse-time cycle detection and a runtime no-progress guard.
- ✅ Task registry pattern with real task implementations (`parse_text`, `classify_with_llm`, `send_notification`).
- ✅ Standard service spine: health endpoint, config, structured logging, comprehensive tests.

---

## Milestone 2: Asynchronous Scaling & Resilience ✅ (Completed)

- ✅ **Celery dispatch**: `run_workflow_task` runs a full workflow in a background worker via `shared_core.tasks.create_celery_app`; importable without a broker. Opt-in per request or via `WORKFLOW_ASYNC`.
- ✅ **Retry & backoff**: per-step `retries` enforced with capped exponential backoff (injectable sleep for tests).
- ✅ **Dead-letter queue**: failed steps quarantined with error/attempts/params; queryable via `GET /workflows/dead-letters`.
- ✅ **Conditional branching**: steps gated on prior results (`equals`/`contains`/`not_equals`); non-matching steps `SKIPPED` without deadlock.
- ✅ **Manual rerun**: `POST /workflows/{run_id}/rerun` re-executes the stored definition under the same id.
- ✅ **DAG projection API**: `GET /workflows/{run_id}/dag` returns `{nodes, edges, status}` for a dashboard.

---

## Milestone 3: Persistence, Scheduling & Triggers ✅ (Completed)

- ✅ **PostgreSQL persistence by default** with in-memory fallback (`db_available` probe); Alembic migration for `workflow_runs` + `step_executions`.
- ✅ **Cron scheduling**: `WorkflowScheduler` (croniter) registers workflows and computes due runs; `POST /schedules`, `GET /schedules`, `DELETE /schedules/{name}`, `POST /schedules/run-due`.
- ✅ **Webhook triggers**: register a workflow under a name and fire it with `POST /webhooks/{name}`.

---

## Milestone 4: Production Hardening (Future)

- **Parallel fan-out**: execute independent steps within a run concurrently (thread/async pool or per-step Celery dispatch).
- **Celery-beat scheduling**: fire due schedules automatically instead of a manual tick.
- **Persistent registries**: store schedules and webhook triggers in PostgreSQL so they survive restarts.
- **Typed step I/O**: a contract for piping structured (validated) data between steps rather than stringified results.
- **AuthN/AuthZ**: API authentication, webhook signature verification, per-workflow RBAC, rate limiting (`shared_core.ratelimit`).
- **OpenTelemetry tracing**: spans from trigger → run → step via `shared_core.tracing`.
- **Distributed locks**: `RedisManager` locks to prevent concurrent execution of the same scheduled workflow instance.
- **Workflow versioning**: store and pin definition versions for reproducible reruns.
