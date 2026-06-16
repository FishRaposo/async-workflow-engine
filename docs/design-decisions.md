# Design Decisions

This document records the key architectural choices made during the development of the Async Workflow Engine, using a lightweight ADR (Architecture Decision Record) format.

## Decision 1: Use of Shared Core Utilities

- **Context**: Every project in the showcase portfolio needs boilerplate code for database connections, logging configuration, Redis management, and error base classes. Duplicating this across 12 repositories creates maintenance burden and inconsistency.
- **Options**:
  1. Duplicate the utilities inside each repository.
  2. Implement a local package `shared-core` that projects can depend on via `pip install -e ../shared-core`.
- **Choice**: Option 2.
- **Tradeoff**: Increases alignment across repos and ensures a single bug-fix location. However, requires installing `shared-core` locally before working on any child repository, and the relative path install (`../shared-core`) won't work in isolated CI environments without a workaround (monorepo checkout, git submodule, or private PyPI).

## Decision 2: Docker Compose for Local Isolation

- **Context**: The workflow engine depends on PostgreSQL (for future persistence) and Redis (for Celery broker and health checks). Developers need these services running locally.
- **Options**:
  1. Rely on host-installed PostgreSQL and Redis.
  2. Configure `docker-compose.yml` for isolated container setups.
- **Choice**: Option 2.
- **Tradeoff**: High reproducibility—any developer can `make docker-up` and have identical infrastructure. Zero dependency pollution on the host machine. Takes slightly more disk space for Docker volumes. The `pgvector/pgvector:pg16` image is shared across the portfolio, so the image pull is amortized.

## Decision 3: YAML for Workflow Definitions

- **Context**: Workflows need to be defined declaratively—specifying steps, task mappings, dependencies, and retry policies. The definition format determines how users author workflows and how the system parses them.
- **Options**:
  1. **Python code** — Define workflows as Python classes or decorated functions (like Prefect/Airflow).
  2. **JSON** — Structured, widely supported, but verbose and lacks comments.
  3. **YAML** — Human-readable, supports comments, widely used for infrastructure-as-code (Kubernetes, GitHub Actions, Docker Compose).
  4. **Custom DSL** — Maximum expressiveness, but requires building a parser.
- **Choice**: Option 3 (YAML).
- **Tradeoff**: YAML is familiar to anyone who has written a `docker-compose.yml` or GitHub Actions workflow. It's concise enough for small DAGs and supports inline comments for documentation. The downside is that YAML has well-known parsing pitfalls (indentation sensitivity, implicit type coercion like `yes` → `True`), but `yaml.safe_load()` combined with Pydantic validation in `WorkflowConfig` catches structural errors early. Using YAML also means workflows are data, not code—they can be stored in a database, version-controlled as config files, or submitted via API without running arbitrary Python.

## Decision 4: In-Process DAG Executor with Celery Dispatch at the Run Level

- **Context**: The workflow engine needs to execute multi-step DAGs with dependency ordering. Celery provides `chain()`, `group()`, and `chord()` primitives for per-task orchestration. Alternatively, the executor can manage DAG resolution in-process and Celery can dispatch whole *runs*.
- **Options**:
  1. **Celery primitives** — Model each workflow as a Celery chain/chord; let Celery handle step ordering and retry.
  2. **In-process executor, sync only** — `WorkflowExecutor` resolves the DAG in a single loop in the request thread.
  3. **In-process executor + run-level Celery dispatch** — The executor owns DAG resolution; a Celery task (`run_workflow_task`) runs the *entire* workflow in the background.
- **Choice**: Option 3.
- **Tradeoff**: Keeping DAG resolution in-process means the whole execution flow lives in one `execute()` method — trivial to debug and test, with deadlock detection as a simple loop condition. Pushing the *run* (not each step) onto Celery gets background execution and horizontal scaling without scattering DAG state across broker queues, and keeps retries/branching/DLQ logic in one place. `runner.run_workflow()` is shared verbatim by the synchronous API path and the Celery worker, so the two paths can never diverge. The cost: a single run does not parallelize its independent steps across workers (they run in dependency order within one process). That is an explicit, documented limitation with a clear upgrade path (Option 1/parallel fan-out) if throughput-per-run ever matters.

## Decision 8: PostgreSQL Persistence by Default with In-Memory Fallback

- **Context**: Runs should be durable (a dashboard needs history, rerun needs the original definition), but tests, demos, and offline development must work with no database.
- **Options**:
  1. In-memory only (simple, but loses history and can't be a real service).
  2. PostgreSQL required (durable, but breaks offline/test/demo flows).
  3. Probe the DB at startup; use PostgreSQL when reachable, fall back to in-memory otherwise.
- **Choice**: Option 3, mirroring the `db_available` probe pattern used across the migrated portfolio services.
- **Tradeoff**: `db.probe_database()` runs a cheap `SELECT 1` (with a 2s connect timeout so it fails fast) and caches `db_available`; `get_storage()` returns `DatabaseWorkflowStorage` or `InMemoryWorkflowStorage` accordingly. Both backends expose the *same* method surface, so the rest of the system is oblivious to which is active. The cost is two code paths to keep in sync — addressed by a shared test suite (`test_runner.py` exercises both) and a `MockDatabase`-backed `test_storage_db.py` that runs the real SQLAlchemy path on in-memory SQLite.

## Decision 9: Conditional Branching via Declared Conditions, Not Code

- **Context**: Real workflows need to route — notify sales only if a lead is classified `business`, quarantine only if `spam`. Conditions must stay declarative (workflows are data, not code).
- **Options**:
  1. Embed Python/expression strings in YAML and `eval` them (powerful, unsafe).
  2. A small, typed condition object (`step` + one of `equals`/`contains`/`not_equals`).
- **Choice**: Option 2 (`StepCondition`).
- **Tradeoff**: A typed condition keeps the safe-by-construction property (no `eval`, no arbitrary code) and is trivial to validate and render in a UI. A non-matching step is marked `SKIPPED` and counts as *resolved*, so downstream steps don't deadlock waiting on it. The condition's source step is treated as an implicit dependency so ordering and cycle detection stay correct. The cost is limited expressiveness (no boolean composition yet) — a deliberate trade for safety and clarity.

## Decision 10: A Dead-Letter Queue Instead of Aborting the Run

- **Context**: When a step exhausts its retries, the run shouldn't simply 500 and lose the failure context.
- **Choice**: Failed steps are recorded in the executor's `dead_letters` list (task, error, attempts, params) and persisted on the run (`dead_letters` JSON column / in-memory field). The run completes with `overall_status = "failed"` rather than raising.
- **Tradeoff**: Independent branches still complete, and operators get a queryable record (`GET /workflows/dead-letters`) plus a one-call rerun (`POST /workflows/{id}/rerun`). The cost is that a partial failure returns HTTP 200 with `status: "failed"` — callers must inspect the body, the same contract as the graceful-degradation health check.

## Decision 5: Task Registry Pattern

- **Context**: YAML workflow definitions reference tasks by string name (e.g., `task: parse_text`). The system needs to map these names to executable Python functions at runtime.
- **Options**:
  1. **Dynamic import** — Use `importlib` to resolve task names to module paths (e.g., `workflow_engine.tasks.parse_text`).
  2. **Decorator-based registration** — Tasks self-register via a `@register_task("name")` decorator.
  3. **Explicit registry dict** — A `TASK_REGISTRY` dictionary in `tasks.py` maps names to callables.
  4. **Class-based tasks** — Each task is a class with an `execute()` method, discovered via metaclass or plugin loader.
- **Choice**: Option 3 (explicit registry dict).
- **Tradeoff**: The explicit dict is the simplest pattern that works. Adding a new task requires two things: write the function, add it to `TASK_REGISTRY`. There's no magic, no metaclass, no decorator side effects—a reader can look at `TASK_REGISTRY` and immediately see every available task. The tradeoff is manual bookkeeping: if you write a function but forget to add it to the registry, it won't be discovered. For a showcase project with a small task set, this is acceptable. The migration path to a decorator pattern is trivial if the task count grows.

## Decision 6: Pydantic Models for Workflow Schema Validation

- **Context**: YAML input from users needs structural validation before execution. Invalid definitions (missing step IDs, unknown fields, wrong types) should fail fast with clear error messages.
- **Options**:
  1. **Manual validation** — Write custom validation logic after `yaml.safe_load()`.
  2. **JSON Schema** — Define a JSON Schema and validate the parsed dict.
  3. **Pydantic models** — Define `WorkflowConfig` and `StepConfig` as Pydantic `BaseModel` subclasses.
- **Choice**: Option 3 (Pydantic).
- **Tradeoff**: Pydantic v2 provides type coercion, default values (`retries: int = 3`, `depends_on: Optional[List[str]] = []`), and detailed validation error messages out of the box. Since FastAPI already depends on Pydantic, there's no additional dependency cost. The models serve double duty as both validation layer and type-safe data containers that `WorkflowExecutor` consumes. The only downside is that Pydantic's error messages can be verbose for end users—future work could wrap them in friendlier messages.

## Decision 7: Synchronous Health Checks with Graceful Degradation

- **Context**: The `/health` endpoint needs to report on PostgreSQL and Redis availability. If one service is down, the system should report degraded status rather than crashing.
- **Options**:
  1. **Hard failure** — If any dependency is down, return 500.
  2. **Graceful degradation** — Check each dependency independently, report per-service status, return 200 with `"status": "degraded"`.
- **Choice**: Option 2.
- **Tradeoff**: The health endpoint always returns 200, making it usable by load balancers that distinguish between "service is running" and "service is fully healthy." The `dependencies` object provides granular visibility. The tradeoff is that a simple `curl` check won't catch degraded state unless the caller inspects the JSON body—a monitoring system should check the `status` field, not just the HTTP status code.
