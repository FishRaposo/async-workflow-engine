# Async Workflow Engine

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: MVP](https://img.shields.io/badge/status-MVP-yellow)

**A declarative workflow orchestration engine that parses YAML definitions into executable DAGs, resolves dependencies in topological order, and tracks step-level status through a FastAPI interface.**

## Why This Exists

Backend systems routinely need to coordinate multi-step processes—data ingestion pipelines, lead intake flows, notification chains—where tasks depend on each other and failures must be handled gracefully. Off-the-shelf orchestrators (Airflow, Prefect, Temporal) are powerful but heavyweight; they obscure the underlying mechanics of DAG resolution, dependency tracking, and retry logic behind layers of abstraction.

This project builds a workflow engine from first principles. It demonstrates that the author understands how orchestration systems actually work: topological dependency resolution, task state machines, registry-based dispatch, deadlock detection, and structured error propagation—without hiding behind a framework.

## What It Demonstrates

- **DAG execution engine** — `WorkflowExecutor` resolves step dependencies and executes tasks in topological order with deadlock detection
- **Declarative YAML configuration** — Workflows are defined as data, not code; `parser.py` validates definitions through Pydantic models (`WorkflowConfig`, `StepConfig`)
- **Task registry pattern** — `TASK_REGISTRY` maps string names to callable functions, enabling dynamic dispatch without import coupling
- **Step-level state machine** — Each step tracks status through `PENDING → RUNNING → COMPLETED/FAILED` transitions
- **Structured error handling** — Custom error hierarchy extending `shared_core.errors.BaseApplicationError` with global FastAPI exception handlers
- **Health monitoring** — `/health` endpoint probes both PostgreSQL and Redis dependencies, reporting granular per-service status
- **Celery worker scaffold** — Background task infrastructure configured with Redis broker for async execution path
- **Clean separation of concerns** — Parser, executor, task registry, storage, worker, and API layer each in dedicated modules

## Architecture

```mermaid
graph TB
    Client["HTTP Client"] -->|POST /workflows/run| API["FastAPI App<br/>main.py"]
    Client -->|GET /health| API

    API -->|yaml_definition| Parser["YAML Parser<br/>parser.py"]
    Parser -->|WorkflowConfig| Executor["WorkflowExecutor<br/>executor.py"]
    Executor -->|step.task lookup| Registry["TASK_REGISTRY<br/>tasks.py"]
    Registry -->|callable| Executor
    Executor -->|statuses dict| API

    API -->|health probe| DB["PostgreSQL<br/>pgvector:pg16"]
    API -->|health probe| Redis["Redis 7"]

    Worker["Celery Worker<br/>worker.py"] -->|broker/backend| Redis
    Storage["InMemoryWorkflowStorage<br/>storage.py"] -.->|future| DB

    style API fill:#009688,color:#fff
    style Executor fill:#1565c0,color:#fff
    style Parser fill:#7b1fa2,color:#fff
    style Registry fill:#e65100,color:#fff
```

## Tech Stack

| Component | Choice | Justification |
|-----------|--------|---------------|
| **API Framework** | FastAPI 0.100+ | Async-ready, auto-generated OpenAPI docs, Pydantic integration |
| **YAML Parsing** | PyYAML 6.0+ | Industry standard; `yaml.safe_load` prevents code execution |
| **Validation** | Pydantic v2 | `WorkflowConfig` and `StepConfig` models enforce schema at parse time |
| **Task Queue** | Celery 5.3+ | Production-proven distributed task execution with Redis broker |
| **Database** | PostgreSQL 16 (pgvector) | Relational storage for workflow runs; pgvector image shared across portfolio |
| **Cache/Broker** | Redis 7 | Celery broker, health check target, future run-state caching |
| **ORM** | SQLAlchemy 2.0+ | Database abstraction with connection pooling; used in health checks |
| **Logging** | Loguru 0.7+ | Structured logging with step-level execution tracing |
| **Shared Library** | `shared-core` | Config, database, Redis, logging, and error base classes |

## Local Setup

```bash
# 1. Clone the portfolio and navigate to this project
cd async-workflow-engine

# 2. Start infrastructure
make docker-up        # Launches PostgreSQL and Redis containers

# 3. Install dependencies (installs shared-core first)
make install

# 4. Copy environment config
cp .env.example .env

# 5. Run the API server
make dev              # Starts uvicorn via src/workflow_engine/main.py

# 6. Run the demo
make demo             # Executes examples/run_demo.py
```

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- `shared-core` sibling directory (installed automatically by `make install`)

## Demo

The demo (`examples/run_demo.py`) executes a three-step `lead_intake` workflow without starting the API server:

```bash
make demo
```

**What it does:**
1. Parses an inline YAML workflow definition with three steps: `parse_input → classify → notify`
2. Instantiates `WorkflowExecutor` with the parsed `WorkflowConfig` and `TASK_REGISTRY`
3. Executes steps in dependency order — `parse_text()`, then `classify_with_llm()`, then `send_notification()`
4. Prints the final status map

**Expected output:**
```
--- Running Workflow Engine Scaffolding Demo ---
Execution results: {'parse_input': 'COMPLETED', 'classify': 'COMPLETED', 'notify': 'COMPLETED'}
```

You can also test via the API:

```bash
curl -X POST http://localhost:8000/workflows/run \
  -H "Content-Type: application/json" \
  -d '{"yaml_definition": "name: test\nsteps:\n  - id: step1\n    task: parse_text\n"}'
```

## Tests

```bash
make test
```

Current test coverage (`tests/test_core.py`):
- **Health endpoint** — Verifies `GET /health` returns 200 with service name `async-workflow-engine` and a `dependencies` object

Planned test additions:
- YAML parsing with valid/invalid/malformed definitions
- DAG execution with linear, fan-out, and diamond dependencies
- Deadlock detection on cyclic graphs
- Task registry miss handling
- Retry policy enforcement
- Step status transition correctness

## API Reference

### `POST /workflows/run`

Accepts a YAML workflow definition and executes it synchronously.

**Request body:**
```json
{
  "yaml_definition": "name: lead_intake\nsteps:\n  - id: parse_input\n    task: parse_text\n"
}
```

**Response (200):**
```json
{
  "workflow": "lead_intake",
  "step_statuses": {
    "parse_input": "COMPLETED"
  }
}
```

**Error (400):** Returned for invalid YAML, missing tasks in registry, or execution failures.

### `GET /health`

Returns infrastructure health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "async-workflow-engine",
  "dependencies": {
    "database": "online",
    "redis": "online"
  }
}
```

## Configuration

Key environment variables from `.env.example`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_NAME` | `async-workflow-engine` | Service identifier in logs and health responses |
| `ENV` | `development` | Runtime environment flag |
| `DEBUG` | `true` | Debug mode toggle |
| `LOG_LEVEL` | `INFO` | Loguru logging verbosity |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/postgres` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery broker and health checks |

## Known Limitations

1. **Synchronous execution by default** — `WorkflowExecutor.execute()` runs synchronously; Celery-based async dispatch is scaffolded in `worker.py` but not wired to the executor's main path
2. **In-memory storage is default** — `InMemoryWorkflowStorage` is the default backend and loses data on restart; `DatabaseWorkflowStorage` exists and is feature-complete but not yet wired as the default
3. **Celery worker scaffold only** — `worker.py` defines a Celery app and sample task; the executor does not yet dispatch to Celery for true background execution
4. **No workflow history UI** — `GET /workflows/{run_id}` returns status but there's no dashboard or visual DAG view for inspecting past runs
5. **No scheduling or webhooks** — Workflows can only be triggered via API POST; no cron-style scheduling or webhook triggers
6. **No conditional branching** — Steps always follow the declared DAG; no runtime conditional branching based on step output

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the full phased plan. Summary:

- **Phase 1 (Display-Ready):** Retry logic, step I/O piping, PostgreSQL persistence, workflow status API, Celery-based async execution
- **Phase 2 (Showcase):** Webhook triggers, scheduled workflows, dead-letter queue, manual rerun, visual DAG graph
- **Phase 3 (Future):** Conditional branching, parallel fan-out, workflow versioning, OpenTelemetry tracing

## Related Projects

This is a **Wave 1** project in the [AI Infrastructure Showcase Portfolio](../). It provides foundational orchestration patterns that feed into:

- **[hermes-agent-framework](../hermes-agent-framework)** — Uses workflow engine patterns for agent tool orchestration
- **[document-intelligence-pipeline](../document-intelligence-pipeline)** — Applies similar DAG-based processing for document ingestion
- **[shared-core](../shared-core)** — Provides the base config, database, Redis, logging, and error infrastructure used here
