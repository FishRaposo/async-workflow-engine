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

## Decision 4: In-Process DAG Executor vs. Celery Task Chains

- **Context**: The workflow engine needs to execute multi-step DAGs with dependency ordering. Celery provides `chain()`, `group()`, and `chord()` primitives for task orchestration. Alternatively, the executor can manage DAG resolution in-process.
- **Options**:
  1. **Celery primitives** — Model workflows as Celery chains/chords, let Celery handle ordering and retry.
  2. **In-process executor** — `WorkflowExecutor` class manages dependency resolution, task dispatch, and status tracking in a single synchronous loop.
  3. **Hybrid** — In-process DAG resolution with Celery dispatch for individual tasks.
- **Choice**: Option 2 for MVP, with migration path to Option 3.
- **Tradeoff**: The in-process executor is dramatically simpler to debug, test, and reason about. The entire execution flow is visible in a single `execute()` method—no distributed state to chase across broker queues. Deadlock detection is a simple loop condition check. The cost is that execution blocks the API request thread and cannot scale horizontally. For showcase purposes, this tradeoff is acceptable: the system demonstrates DAG resolution mechanics clearly, and the `worker.py` Celery scaffold proves the author knows how to integrate distributed dispatch when needed. The migration path is clear: replace `task_fn()` calls in the executor with `celery_app.send_task()` calls and poll for results.

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
