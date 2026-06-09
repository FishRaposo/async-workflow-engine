# Project Roadmap - Async Workflow Engine

This document outlines the milestones and roadmap phases for the Async Workflow Engine.

---

## Milestone 1: Core DAG Engine (Completed)
- **Declarative YAML parser**: Validate workflow formats using Pydantic configurations.
- **In-process Topological Executor**: Run workflows in dependency order with cyclic loop and deadlock detection.
- **Task Registry Pattern**: Pre-register task functions (`parse_text`, `classify_with_llm`, `send_notification`) to execute dynamically.
- **Standard Service Infrastructure**: Health check endpoint, configuration mapping, logging integration, and basic test coverage.

---

## Milestone 2: Asynchronous Scaling & Showcase UI (Planned)
- **Celery Worker Integration**: Move workflow execution out of the FastAPI request-response thread into independent background Celery workers using Redis as a broker.
- **Retry and Backoff Enforcement**: Fully implement and test step-level retry parameters (`step.retries`) with configurable backoff policies.
- **Visual DAG Dashboard**: A lightweight frontend/admin view displaying active/completed runs, step statuses (PENDING, RUNNING, COMPLETED, FAILED), and execution latency per node.
- **Dead-Letter Queue (DLQ)**: Quarantine failed steps for manual inspection, debugging, and task re-runs.

---

## Milestone 3: Production Readiness (Future)
- **Persistent Runs Database**: Save workflow definitions, run history, and step logs to PostgreSQL (via SQLAlchemy schema).
- **Scheduled Workflows**: Build a scheduler system (similar to cron or Celery beat) to trigger workflows at defined intervals.
- **Distributed Lock Management**: Leverage Redis distributed locks (`RedisManager` lock utils) to prevent concurrent executions of the same workflow instance.
- **OpenTelemetry Tracing**: Implement comprehensive tracing to trace context from webhook triggers through workflow execution down to individual step executions.
