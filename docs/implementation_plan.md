# Implementation Plan - Async Workflow Engine

This document details the step-by-step technical implementation plan and development milestones for **Async Workflow Engine**.

---

## 1. Project Goal
A YAML-configured directed acyclic graph (DAG) execution engine that runs background workflows using Celery and Redis, exposing a REST API for run submission and lifecycle tracking.

---

## 2. Architecture & Component Map

The repository is structured as a standalone project conforming to operator workspace standards. The core module responsibilities are mapped below:

### 2.1 File Map & Responsibilities
* **`src/workflow_engine/parser.py`**: Parses YAML workflow definitions, validates steps with Pydantic, and builds the execution DAG.
* **`src/workflow_engine/executor.py`**: Traverses DAG topology, detects cycle deadlocks, schedules independent steps, and handles step-level failures.
* **`src/workflow_engine/tasks.py`**: Registry of executable task functions (e.g., text parsing, mock LLM, notification triggers).
* **`src/workflow_engine/worker.py`**: Celery application orchestrating async task execution workers.
* **`src/workflow_engine/storage.py`**: Handles state persistence of workflow runs, step durations, and execution results.

### 2.2 Shared Core Dependencies
This service imports standard layers from `shared-core` (sibling dependency library):
* `shared_core.config.BaseAppConfig`: Settings parsing, reading configs from `.env`.
* `shared_core.database.DatabaseManager`: SQL database engine instantiation and session factories.
* `shared_core.redis.RedisManager`: Caching connections and health checks.
* `shared_core.logging.setup_logging`: Structured log formats and correlation ID tracing.
* `shared_core.errors.BaseApplicationError`: Exception mapping and global handlers.

---

## 3. Database Schema & Data Models

### 3.1 Data Schema
PostgreSQL: `workflows` (id, name, yaml_definition, created_at), `workflow_runs` (id, workflow_id, status, started_at, completed_at), `step_runs` (id, run_id, step_name, status, input_data, output_data, error_message, latency_ms).
Redis: Celery task broker queue and key lock state storage.

### 3.2 Redis Storage & Caching Patterns
* Caching: Utilizing `@cache` decorator with prefix keys.
* Concurrency: Lock critical tasks using `RedisLock` context managers.

---

## 4. Step-by-Step Implementation Sequence

The project development checklist is ordered into six milestones:

- `[ ]` **Milestone 1 (Design): Design schema for runs/steps and DAG topological sort.**
- `[ ]` **Milestone 2 (Skeleton): Create Celery config, FastAPI wrapper, and database connection pools.**
- `[ ]` **Milestone 3 (Core Loop): Build YAML parser and in-memory round-robin DAG executor.**
- `[ ]` **Milestone 4 (Reliability): Integrate Redis task locking to prevent duplicate workflow launches.**
- `[ ]` **Milestone 5 (Showcase): Build a CLI workflow demo executing a multi-step parsing and summarization DAG.**
- `[ ]` **Milestone 6 (Publish): Document failure modes, deadlocks, and retry configurations.**

---

## 5. Standard Makefile & Developer Commands

```bash
make install          # Set up virtual environment and local editable package
make dev              # Boot the microservice API server locally
make test             # Run local pytest / jest test suites
make lint             # Execute Ruff checks / ESLint verifications
make format           # Standardize style formatting
make typecheck        # Verify static types (Pyright / TypeScript)
make docker-up        # Spawn isolated local PostgreSQL and Redis service containers
make docker-down      # Teardown the isolated local containers stack
make demo             # Execute the runnable demo workflow
make clean            # Remove caches and temporary files
```

---

## 6. Verification & Testing Plan

### 6.1 Automated Tests
* **Core Logic Verification**: Tests for DAG circular reference detection, step status transitions, mock Celery tasks, and execution persistence.
* **Type Safety & Style**: Run `make typecheck` and `make lint` as a pipeline validation hook.
* **Mock Environments**: Utilize `MockDatabase` and `MockRedisClient` inside `tests/conftest.py` to assert correct lifecycle transactions without depending on live network services.

### 6.2 Manual Verification
* Deploy local PostgreSQL and Redis containers with `make docker-up`.
* Execute the runnable script demo `make demo` and review Loguru stdout records.
