# Failure Modes & Mitigation

This reference guide outlines predictable failure conditions within the Async Workflow Engine, detailing their operational manifestations, detection rules, and recovery steps.

## 1. Database Connectivity Failure

- **Cause**: PostgreSQL container down, network partition, or connection pool exhaustion.
- **Impact**: `/health` endpoint reports `"database": "offline"` and overall status `"degraded"`. Future persistence writes will fail. Current workflow execution is unaffected (does not depend on PostgreSQL at runtime).
- **Detection**: `GET /health` returns `{"status": "degraded", "dependencies": {"database": "offline"}}`. Logs contain SQLAlchemy connection timeout errors.
- **Mitigation**: `docker compose up -d postgres` to restart. SQLAlchemy connection pooling with `pool_pre_ping=True` (configured in `shared_core.database.DatabaseManager`) automatically recovers stale connections.
- **Future Fix**: Add auto-restart policies in Docker Compose (`restart: unless-stopped`). Implement circuit breaker on database calls. Add PostgreSQL connection pool metrics to health response.

## 2. Queue Backlog / Worker Starvation

- **Cause**: Spike in workflow submissions, slow task execution (e.g., LLM API timeouts in `classify_with_llm`), or Celery worker process crash.
- **Impact**: If/when Celery dispatch is active, tasks remain in Redis queues indefinitely. API response times increase if execution is synchronous. Steps stay in `PENDING` or `RUNNING` state.
- **Detection**: Redis queue length monitoring (`LLEN` on Celery queues). Celery worker heartbeat absence. Log warnings for tasks exceeding expected duration.
- **Mitigation**: Tune worker concurrency (`--concurrency` flag). Apply timeouts on all outbound HTTP requests in task functions. Monitor Redis memory usage.
- **Future Fix**: Implement dead-letter queue for tasks that exceed max retry attempts. Add Flower dashboard for real-time Celery monitoring. Set `task_time_limit` and `task_soft_time_limit` in Celery config.

## 3. DAG Deadlock (Cyclic Dependencies)

- **Cause**: A workflow definition contains a circular dependency chain (e.g., step A depends on step B, step B depends on step A). This can also occur with indirect cycles through three or more steps.
- **Impact**: `WorkflowExecutor.execute()` enters its main loop but no step can ever have its dependencies met. The deadlock detection logic fires when a full iteration round completes with `executed_this_round = False` while uncompleted steps remain. The executor logs an error and **breaks out of the loop silently**, returning a partial status map where cyclic steps remain `PENDING`.
- **Detection**: Log line: `"Deadlock detected or dependency loop in DAG execution."` The response will contain steps with `PENDING` status that were never executed.
- **Mitigation**: Inspect the YAML definition for circular `depends_on` references. The current implementation does not raise an exception on deadlock—it returns partial results.
- **Future Fix**: Add a pre-execution cycle detection pass using topological sort (Kahn's algorithm or DFS-based). Reject cyclic definitions at parse time with a clear error message listing the cycle path. Consider adding a `WorkflowValidationError` that fires before execution begins.

## 4. Task Registry Miss

- **Cause**: A workflow YAML references a task name (e.g., `task: send_email`) that is not registered in `TASK_REGISTRY`. This happens when YAML definitions are authored without checking available tasks, or when a task is removed from the registry without updating workflow definitions.
- **Impact**: `WorkflowExecutor.execute()` calls `self.task_registry.get(step.task)` and receives `None`. The step is immediately marked `FAILED`, and a `ValueError(f"Task {step.task} missing")` is raised. This halts the entire workflow—no subsequent steps execute, even if they don't depend on the failed step.
- **Detection**: Log line: `"Task {name} not found in registry!"` API returns 400 with `ValueError` detail message.
- **Mitigation**: Validate all task references at parse time before execution begins. Check `set(step.task for step in config.steps) - set(TASK_REGISTRY.keys())` and fail fast.
- **Future Fix**: Add a `validate()` method to `WorkflowExecutor` that checks all task references and dependencies before `execute()`. Add a `GET /tasks` endpoint listing available tasks so workflow authors can verify names. Consider graceful handling that marks only the affected step as `FAILED` without halting the entire workflow.

## 5. YAML Parse Errors

- **Cause**: Malformed YAML syntax (bad indentation, unmatched quotes, invalid characters) or valid YAML that doesn't match the `WorkflowConfig` schema (missing `name` field, `steps` is not a list, unknown `depends_on` format).
- **Impact**: Two failure paths:
  1. **YAML syntax error**: `yaml.safe_load()` raises `yaml.YAMLError` → caught by `run_workflow()` → 400 response.
  2. **Schema validation error**: Pydantic `ValidationError` in `WorkflowConfig(**data)` → caught → 400 response with validation details.
- **Detection**: API returns HTTP 400. Error detail contains either YAML parser error message or Pydantic validation error listing (field name, error type, message).
- **Mitigation**: Use `examples/sample_workflow.yaml` as a reference template. Validate YAML locally before submitting to the API.
- **Future Fix**: Add a `POST /workflows/validate` endpoint that parses and validates without executing. Return structured validation results with line numbers for YAML errors. Add JSON Schema export for IDE-based YAML validation.

## 6. Task Function Exception

- **Cause**: A registered task function raises an unhandled exception during execution. Currently the stub tasks (`parse_text`, `classify_with_llm`, `send_notification`) are trivial and unlikely to fail, but real implementations will make HTTP calls, database queries, or LLM API calls that can fail.
- **Impact**: The step is marked `RUNNING` → `FAILED`. The exception is re-raised from `WorkflowExecutor.execute()`, which propagates to `run_workflow()` and returns an HTTP 400. **All downstream steps are never attempted**, even if they don't depend on the failed step—the exception halts the entire workflow.
- **Detection**: Log line: `"Step {id} failed: {error}"`. API returns 400 with exception detail.
- **Mitigation**: Wrap task functions in try/except with appropriate error handling. Use `StepConfig.retries` field (parsed but not yet enforced) to retry transient failures.
- **Future Fix**: Implement retry logic in the executor that respects `step.retries`. Add exponential backoff between retries. Allow workflows to define `on_failure: continue` to skip failed steps and proceed with independent branches. Move failed tasks to a dead-letter queue for manual inspection and rerun.

## 7. Redis Connectivity Failure

- **Cause**: Redis container down, port conflict on 6379, or memory exhaustion.
- **Impact**: `/health` reports `"redis": "offline"`. Celery worker cannot start or process tasks. If Redis is used for result caching in the future, cached data becomes unavailable. Current synchronous workflow execution is unaffected.
- **Detection**: `GET /health` response shows `"redis": "offline"`. `RedisManager.ping()` raises `ConnectionError`. Celery worker logs connection refused errors.
- **Mitigation**: `docker compose up -d redis` to restart. Check for port conflicts (`netstat -tlnp | grep 6379`). Verify Redis memory limits.
- **Future Fix**: Add Redis sentinel or cluster mode for high availability. Implement connection retry with backoff in `RedisManager`. Add Redis memory usage to health check response.

## 8. Concurrent Workflow Submissions (Future Risk)

- **Cause**: Multiple simultaneous `POST /workflows/run` requests while execution is synchronous and in-process.
- **Impact**: Each request blocks a uvicorn worker thread for the duration of workflow execution. With slow tasks (LLM calls, HTTP requests), this can exhaust the worker pool and cause request queuing or timeouts for all endpoints, including `/health`.
- **Detection**: Increasing response times on `/health`. Uvicorn access logs show queued requests. HTTP 503 errors from upstream load balancers.
- **Mitigation**: Currently mitigated by tasks being trivial stubs (sub-millisecond execution). Set uvicorn worker count appropriately for expected load.
- **Future Fix**: Move workflow execution to Celery workers (the `worker.py` scaffold exists for this purpose). API returns a `run_id` immediately and execution happens asynchronously. Add a `GET /workflows/{run_id}/status` endpoint for polling.
