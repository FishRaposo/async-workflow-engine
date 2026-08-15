# Task 2 report — workflow-owned core capabilities

## Scope delivered

This slice adds additive workflow-owned capability contracts without changing the
default HTTP or execution path. Existing `WorkflowExecutor`, runner, scheduler,
webhook registry, storage facades, YAML semantics, and Celery import behavior
remain usable as before.

- `contracts.py`: structural `WorkflowStorage`, `ScheduleStore`, and
  `WebhookStore` contracts; typed `TaskInput`/`TaskResult`, typed-task adapter
  `TaskRunner`, and a process-local idempotency claim store.
- `trace.py`: ordered clock-free `TraceContext`/`ExecutionEvent` sink. Runner
  emits `trigger.received`; executor emits run, step, retry, failure, DLQ, and
  skipped events deterministically.
- `locks.py`: default `InMemoryLockProvider` plus a caller-supplied-client
  `RedisLockProvider`; importing either does not connect to Redis.
- `auth.py`: disabled-by-default API-key role policy (`viewer`, `operator`,
  `admin`) and per-key/client local fixed-window rate-limit buckets. Route
  enforcement is deliberately deferred to Task 3.
- `versions.py`: canonical YAML content hashes and an in-memory version store.
  `run_workflow(..., version_store=...)` returns an additive `version_hash` and
  can execute a pinned stored definition through `version_hash=`.
- Executor and runner: `concurrency_limit` enables one ready DAG layer to run
  in a bounded thread pool; `typed_io=True` invokes typed task objects while
  default legacy callables and dictionary results are untouched.
- Scheduler and webhook registry: store adapters with in-memory defaults,
  preserved legacy mapping constructors, optional schedule-fire idempotency,
  optional webhook HMAC verification, and an opt-in broker-free Celery-beat
  tick (`WORKFLOW_CELERY_BEAT=1`). Durable database adapters/migrations and API
  wiring remain Task 3 work.

`AppConfig` makes the relevant defaults explicit:
`WORKFLOW_AUTH_REQUIRED=false`, `WORKFLOW_CONCURRENCY_LIMIT=1`,
`WORKFLOW_CELERY_BEAT=false`, and `WORKFLOW_REDIS_LOCKING_ENABLED=false`.

## TDD evidence

1. `tests/test_workflow_core.py` was created before the implementation. Its
   first run failed at collection with `ModuleNotFoundError:
   workflow_engine.auth`.
2. After the initial modules existed, the focused suite failed on the missing
   `InMemoryScheduleStore`, then on the missing `run_workflow(...,
   version_store=...)` seam. Each failure was implemented minimally and rerun
   green.
3. The Celery-beat contract was added before its worker hook and failed with
   `AttributeError: module 'workflow_engine.worker' has no attribute
   'beat_scheduler'`.
4. Self-review found two compatibility defects. Regression tests first showed
   (a) parallel trace output incorrectly recorded a final failed attempt as a
   retry (`[1, 2]` rather than `[1]`), and (b) the legacy
   `WorkflowScheduler({...})` constructor treated the mapping as a store.
   Both were fixed and retained as contracts.

## Verification

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_workflow_core.py -q` | 16 passed |
| `python -m pytest -q -k "not self_containment"` | 138 passed, 3 deselected |
| `python -m ruff check src/workflow_engine tests` | passed |
| `python -m ruff format --check src/workflow_engine tests` | 51 files already formatted |
| `git diff --check` | passed (Git emitted only existing LF-to-CRLF notices) |

The three Task 1 packaging/self-containment tests were intentionally excluded
from the Task 2 regression command because this slice does not touch packaging
or vendored imports. An attempted standalone invocation,
`python -m pytest tests/test_self_containment.py -q`, did not return a terminal
summary through the harness after the wheel-build test started, so it is not
claimed as verified in this task. Task 1's recorded verification remains the
latest evidence for that unaffected package boundary.

## Scope held for Task 3

No database migration, database-backed schedule/webhook/version/idempotency
adapter, FastAPI authorization/rate-limit/HMAC enforcement, tenant model,
external notifications, hosted scheduler, or distributed Celery fan-out was
added. The new interfaces are intentionally injection points for that later
integration work.
