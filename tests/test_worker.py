"""Celery worker tests — run with no broker.

Celery tasks are invoked directly (the underlying ``.run``) and via ``.apply()``
(eager, in-process), so no Redis/broker is needed. The worker probes the DB and
falls back to in-memory storage, then delegates to the shared runner.
"""

import workflow_engine.db as db_module
from workflow_engine.worker import (
    celery_app,
    run_due_schedules,
    run_workflow_task,
)

LINEAR = "name: linear\nsteps:\n  - id: s1\n    task: parse_text\n"


def test_celery_app_configured():
    assert celery_app.main == "async-workflow-engine"
    assert "workflow_engine.run_workflow" in celery_app.tasks


def test_run_workflow_task_executes(monkeypatch):
    # Force the in-memory fallback so no DB is needed.
    monkeypatch.setattr(db_module, "db_available", False)
    monkeypatch.setattr("workflow_engine.worker.probe_database", lambda cfg: False)
    # Invoke the task body eagerly (apply runs in-process, no broker).
    result = run_workflow_task.apply(args=[LINEAR]).get()
    assert result["status"] == "completed"
    assert result["step_statuses"]["s1"] == "COMPLETED"


def test_run_workflow_task_with_run_id(monkeypatch):
    monkeypatch.setattr(db_module, "db_available", False)
    monkeypatch.setattr("workflow_engine.worker.probe_database", lambda cfg: False)
    result = run_workflow_task.apply(args=[LINEAR, "fixed-id"]).get()
    assert result["run_id"] == "fixed-id"


def test_run_due_schedules_callable():
    result = run_due_schedules.apply().get()
    assert result == {"dispatched": []}
