"""Celery worker tests — run with no broker.

Celery tasks are invoked directly (the underlying ``.run``) and via ``.apply()``
(eager, in-process), so no Redis/broker is needed. The worker probes the DB and
falls back to in-memory storage, then delegates to the shared runner.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_worker_and_due_run_honor_typed_io_from_yaml(monkeypatch):
    from workflow_engine import runner as runner_module
    from workflow_engine import worker as worker_module
    from workflow_engine.contracts import TaskInput, TaskResult

    class TypedProbe:
        def run(self, task_input: TaskInput) -> TaskResult:
            return TaskResult.ok({"source": task_input.params["source"]})

    definition = """\
name: typed-worker
typed_io: true
steps:
  - id: only
    task: typed_worker_probe
    retries: 0
    params: {source: yaml}
"""
    monkeypatch.setattr(db_module, "db_available", False)
    monkeypatch.setattr(worker_module, "probe_database", lambda cfg: False)
    monkeypatch.setitem(runner_module.TASK_REGISTRY, "typed_worker_probe", TypedProbe())

    worker_result = run_workflow_task.apply(args=[definition]).get()
    due_result = worker_module._run_due_definition(definition)

    assert worker_result["status"] == "completed"
    assert worker_result["results"]["only"] == "{'source': 'yaml'}"
    assert due_result["status"] == "completed"
    assert due_result["results"]["only"] == "{'source': 'yaml'}"


def test_run_due_schedules_callable():
    result = run_due_schedules.apply().get()
    assert result == {"dispatched": []}


def test_due_schedule_tick_probes_before_resolving_cross_process_services(
    monkeypatch,
):
    from workflow_engine import worker as worker_module

    offline_scheduler = MagicMock()
    offline_scheduler.dispatch_due.return_value = []
    durable_scheduler = MagicMock()
    durable_scheduler.dispatch_due.return_value = [
        {"name": "api-created", "run_id": "run-1"}
    ]
    offline = SimpleNamespace(scheduler=offline_scheduler, idempotency=object())
    durable = SimpleNamespace(scheduler=durable_scheduler, idempotency=object())
    monkeypatch.setenv("WORKFLOW_CELERY_BEAT", "1")
    monkeypatch.setattr(db_module, "db_available", False)

    def probe(config):
        db_module.db_available = True
        return True

    monkeypatch.setattr(worker_module, "probe_database", probe)
    monkeypatch.setattr(
        worker_module,
        "get_runtime_services",
        lambda: durable if db_module.db_available else offline,
    )

    result = run_due_schedules.run()

    assert result == {"dispatched": [{"name": "api-created", "run_id": "run-1"}]}
    durable_scheduler.dispatch_due.assert_called_once()
    offline_scheduler.dispatch_due.assert_not_called()


def test_worker_and_due_run_forward_configured_concurrency_limit(monkeypatch):
    from workflow_engine import worker as worker_module

    services = SimpleNamespace(versions=MagicMock(), events=MagicMock())
    services.versions.get.return_value = object()
    run = MagicMock(return_value={"status": "completed", "run_id": "run-1"})
    monkeypatch.setattr(worker_module.config, "WORKFLOW_CONCURRENCY_LIMIT", 4)
    monkeypatch.setattr(worker_module, "probe_database", lambda config: False)
    monkeypatch.setattr(worker_module, "get_runtime_services", lambda: services)
    monkeypatch.setattr(worker_module, "get_storage", lambda config: object())
    monkeypatch.setattr(worker_module, "run_workflow", run)

    run_workflow_task.run(LINEAR)
    worker_module._run_due_definition(LINEAR)

    assert [call.kwargs["concurrency_limit"] for call in run.call_args_list] == [4, 4]
