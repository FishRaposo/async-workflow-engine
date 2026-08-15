# Task 3 Finalization Report

## Scope completed

- Wired the Task 2 runtime contracts through the existing FastAPI routes without
  removing routes, response keys, status values, YAML semantics, retry/DLQ/rerun
  behavior, or the static dead-letters route ordering.
- Added offline-default runtime services, an opt-in Redis lock adapter, and optional SQLAlchemy stores for
  schedules, webhooks (including optional HMAC secret), deterministic workflow
  definitions, idempotency claims, and ordered execution events.
- Persisted workflow version hashes and traces for normal API/worker runs; reruns
  resolve a recorded version hash when one exists.
- Added a backward-compatible error envelope (`detail` remains present) for
  validation, auth/role, rate-limit, lock, idempotency, persistence, dispatch,
  and HMAC failures.
- Kept auth, rate limiting, locking, HMAC, idempotency, asynchronous dispatch,
  and Celery beat opt-in. Offline synchronous execution remains the default.
- Updated the eager Celery path to use the same runtime services and added
  migration `0002_runtime_persistence` while retaining `0001_initial`.

## TDD evidence

`tests/test_task3_integration.py` was added first and observed red for missing
runtime services, version/trace metadata, HMAC/idempotency enforcement, durable
adapters, and the migration. It is now green and covers API golden metadata,
in-memory/SQLite adapter round trips, due-schedule dispatch, webhook HMAC,
idempotency, and a real Alembic SQLite migration execution.

## Verification

- `python -m pytest tests/test_task3_integration.py -q` — 20 passed
- `python -m pytest -q` — 163 passed
- `python -m ruff check src/workflow_engine tests examples alembic` — passed
- `python -m ruff format --check src/workflow_engine tests alembic` — passed
- `git diff --check` — passed
- `python -m pyright src/` — 16 pre-existing errors in executor, scheduler,
  vendored `vendor_core/llm.py`, and the pre-existing FastAPI exception-handler
  variance; no Task 3-specific type errors remain.

## Explicitly deferred

Hosted/team tenancy, external notification delivery, mandatory infrastructure,
hosted scheduling, Redis-backed runtime stores, and distributed Celery fan-out
remain out of scope and disabled.

## Review fixes

- `db.get_storage()` now retains one process-local `InMemoryWorkflowStorage`
  fallback. An unpatched offline API regression proves POST run, GET run, and
  rerun share it; tests replace that private singleton explicitly for isolation.
- FastAPI `RequestValidationError` now preserves its legacy `detail` list while
  adding `error.code=validation_failed`. A shared wrapper gives all persistence
  read/list/delete/rerun paths the established `detail` plus
  `error.code=persistence_failed` 503 envelope, including async webhook reads.
- `RedisLockProvider.from_manager()` adapts the vendored `RedisManager` lazily;
  main imports Redis safely, selects it only with
  `WORKFLOW_REDIS_LOCKING_ENABLED`, and otherwise remains in-memory/offline.
- The dashboard fixture contract now includes optional version hash and ordered
  execution events, with an isolated frontend Vitest assertion.
- `AGENTS.md` now reports the current 163 backend tests and documents the
  process-stable offline store, opt-in Redis lock, and executed Alembic check.

### TDD and verification evidence

- RED: `python -m pytest tests/test_task3_integration.py -q --basetemp C:\temp\awe-task3-red`
  collected 18: 13 failed (offline storage, validation envelope, persistence
  envelopes, and Redis manager adapter), 4 passed, and 1 setup error because the
  requested base-temp parent did not exist. The command was rerun without that
  invalid base-temp after implementation.
- GREEN: `python -m pytest tests/test_task3_integration.py -q` — 20 passed.
- Full backend: `python -m pytest -q` — 163 passed.
- Backend quality: `python -m ruff check src/workflow_engine tests examples alembic`
  — passed; `python -m ruff format --check src/workflow_engine tests alembic`
  — 57 files already formatted; `git diff --check` — passed.
- Frontend fixture: after `npm.cmd ci --ignore-scripts`,
  `npx.cmd --no-install tsc --noEmit` — passed and
  `npx.cmd --no-install vitest run` — 10 files / 25 tests passed. The existing
  React `act(...)` and Recharts zero-size test warnings remain unrelated.
- `python -m pyright src/` still reports 16 known pre-existing errors in
  executor, scheduler, vendored `vendor_core/llm.py`, and the pre-existing
  FastAPI exception-handler variance; the earlier new lock-adapter error is gone.

### Follow-up review fixes

- `RedisLockProvider` now assigns a UUID owner token to every successful
  acquire and uses Redis Lua compare-and-delete on release. A fake-client
  regression simulates TTL expiry and a second acquisition, proving the old
  owner cannot remove the new owner lock.
- The workflow-run idempotency claim now executes inside the route's protected
  persistence path, so a durable claim failure returns the compatible 503
  `persistence_failed` envelope rather than an unhandled 500.
- RED: `python -m pytest tests/test_task3_integration.py -q` — 2 failed,
  18 passed (constant Redis owner token and idempotency claim outside the
  handler boundary).
- GREEN: `python -m pytest tests/test_task3_integration.py -q` — 20 passed.
- Full regression: `python -m pytest -q` — 163 passed. Ruff check and format,
  plus `git diff --check`, passed; Pyright remains at the same 16 pre-existing
  errors.
- Self-review: confirmed each acquire captures its own token, release is atomic
  compare-and-delete, the default remains in-memory/no-Redis, and the idempotency
  failure is caught by the existing compatible persistence envelope.
