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

- ✅ **Celery dispatch**: `run_workflow_task` runs a full workflow in a background worker via the vendored `create_celery_app`; importable without a broker. Opt-in per request or via `WORKFLOW_ASYNC`.
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

## Milestone 4: Deliberately Deferred Product Work

- **Production deployment validation**: run against a live PostgreSQL, Redis, and Celery worker deployment with production network, credential, and observability controls.
- **Multi-tenant security**: secret rotation, TLS termination, per-workflow RBAC, and distributed rate limiting beyond the local opt-in primitives.
- **Typed step I/O**: a contract for piping structured (validated) data rather than the current task-result convention.
- **OpenTelemetry export**: production tracing/export configuration beyond the deterministic execution-event store.
- **Operations UI**: turn the included offline-capable dashboard into a deployed, authenticated operator surface.
