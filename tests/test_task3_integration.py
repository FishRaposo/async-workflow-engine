"""Task 3 integration contracts for API, durable stores, and eager workers."""

from __future__ import annotations

import hashlib
import hmac
import importlib
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

import workflow_engine.models as models
from alembic import command
from workflow_engine.internal.vendor_core.testing import MockRedisClient
from workflow_engine.storage import InMemoryWorkflowStorage

LINEAR = "name: api-pinned\nsteps:\n  - id: only\n    task: parse_text\n"


def _runtime_services_class():
    try:
        return importlib.import_module("workflow_engine.runtime").RuntimeServices
    except ModuleNotFoundError:
        return None


@pytest.fixture
def client(monkeypatch):
    """Keep the legacy offline default while exposing the new runtime services."""
    from workflow_engine import main as main_module

    monkeypatch.delenv("WORKFLOW_AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("WORKFLOW_RATE_LIMIT", raising=False)
    runtime_services = _runtime_services_class()
    if runtime_services is None:
        from workflow_engine.scheduler import WorkflowScheduler
        from workflow_engine.webhooks import WebhookRegistry

        services = SimpleNamespace(
            scheduler=WorkflowScheduler(), webhooks=WebhookRegistry()
        )
    else:
        services = runtime_services.in_memory()
    storage = InMemoryWorkflowStorage()
    mock_db = MagicMock()
    mock_redis = MagicMock()
    with (
        patch.object(main_module, "_storage", lambda: storage),
        patch.object(main_module, "services", services, create=True),
        patch.object(main_module, "scheduler", services.scheduler),
        patch.object(main_module, "webhooks", services.webhooks),
        patch.object(main_module, "db_manager", mock_db),
        patch.object(main_module, "redis_manager", mock_redis),
        patch.object(main_module, "probe_database", lambda cfg=None: False),
        patch("workflow_engine.db.probe_database", lambda cfg=None: False),
    ):
        with TestClient(main_module.app, raise_server_exceptions=False) as test_client:
            yield test_client, services


@pytest.fixture
def offline_client(monkeypatch):
    """Exercise the offline API without replacing its storage selector."""
    from workflow_engine import db as db_module
    from workflow_engine import main as main_module

    monkeypatch.setattr(db_module, "db_available", False)
    monkeypatch.setattr(
        db_module, "_offline_storage", InMemoryWorkflowStorage(), raising=False
    )
    with (
        patch.object(main_module, "probe_database", lambda cfg=None: False),
        patch("workflow_engine.db.probe_database", lambda cfg=None: False),
    ):
        with TestClient(main_module.app, raise_server_exceptions=False) as test_client:
            yield test_client


def test_run_persists_version_and_trace_and_rerun_uses_pinned_definition(client):
    test_client, services = client
    first = test_client.post("/workflows/run", json={"yaml_definition": LINEAR})

    assert first.status_code == 200
    body = first.json()
    assert len(body["version_hash"]) == 64
    assert [event["kind"] for event in body["events"]] == [
        "trigger.received",
        "run.started",
        "step.started",
        "step.completed",
        "run.finished",
    ]
    assert services.versions.get(body["version_hash"]).yaml_definition == LINEAR

    rerun = test_client.post(f"/workflows/{body['run_id']}/rerun", json={})
    assert rerun.status_code == 200
    assert rerun.json()["version_hash"] == body["version_hash"]


def test_webhook_hmac_and_idempotency_are_only_enforced_when_configured(client):
    test_client, _ = client
    registered = test_client.post(
        "/webhooks/signed/register",
        json={"yaml_definition": LINEAR, "secret": "top-secret"},
    )
    assert registered.status_code == 200

    body = b"{}"
    signature = "sha256=" + hmac.new(b"top-secret", body, hashlib.sha256).hexdigest()
    rejected = test_client.post("/webhooks/signed", content=body)
    assert rejected.status_code == 401
    assert rejected.json()["error"]["code"] == "webhook_signature_invalid"

    accepted = test_client.post(
        "/webhooks/signed",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Idempotency-Key": "one"},
    )
    duplicate = test_client.post(
        "/webhooks/signed",
        content=body,
        headers={"X-Hub-Signature-256": signature, "Idempotency-Key": "one"},
    )
    assert accepted.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "idempotency_conflict"


def test_database_runtime_stores_round_trip_all_task3_records(mock_db):
    runtime_services = _runtime_services_class()
    assert runtime_services is not None, "Task 3 runtime services are not implemented"
    services = runtime_services.database(mock_db.get_session)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    schedule = services.scheduler.register("minute", "* * * * *", LINEAR, now=now)
    services.webhooks.register("hook", LINEAR, "test hook", secret="s")
    version = services.versions.put(LINEAR)
    services.events.save(
        run_id="run-1",
        events=[{"sequence": 1, "kind": "trigger.received", "details": {}}],
    )

    rebuilt = runtime_services.database(mock_db.get_session)
    assert rebuilt.scheduler.store.get("minute").next_run == schedule.next_run
    assert rebuilt.webhooks.get("hook").secret == "s"
    assert rebuilt.versions.get(version.content_hash).yaml_definition == LINEAR
    assert rebuilt.idempotency.claim("workflow", "key") is True
    assert rebuilt.idempotency.claim("workflow", "key") is False
    assert rebuilt.events.list("run-1")[0]["kind"] == "trigger.received"
    assert all(
        model.__table__.name
        in {
            "schedules",
            "webhook_registrations",
            "workflow_definitions",
            "idempotency_records",
            "execution_events",
        }
        for model in (
            getattr(models, "ScheduleRecord", None),
            getattr(models, "WebhookRegistration", None),
            getattr(models, "WorkflowDefinition", None),
            getattr(models, "IdempotencyRecord", None),
            getattr(models, "ExecutionEventRecord", None),
        )
    )


def test_api_schedule_store_is_shared_with_due_dispatch(client):
    test_client, services = client
    created = test_client.post(
        "/schedules",
        json={"name": "minute", "cron": "* * * * *", "yaml_definition": LINEAR},
    )
    assert created.status_code == 200
    schedule = services.scheduler.store.get("minute")
    schedule.next_run = datetime.now(timezone.utc) - timedelta(minutes=1)
    services.scheduler.store.put(schedule)

    due = test_client.post("/schedules/run-due")
    assert due.status_code == 200
    assert due.json()["dispatched"][0]["name"] == "minute"


def test_offline_api_keeps_runs_across_unpatched_storage_requests(offline_client):
    first = offline_client.post("/workflows/run", json={"yaml_definition": LINEAR})
    run_id = first.json()["run_id"]

    found = offline_client.get(f"/workflows/{run_id}")
    rerun = offline_client.post(f"/workflows/{run_id}/rerun", json={})

    assert found.status_code == 200
    assert found.json()["run_id"] == run_id
    assert rerun.status_code == 200
    assert rerun.json()["run_id"] == run_id


def test_malformed_request_uses_compatible_validation_error_envelope(client):
    test_client, _ = client
    response = test_client.post(
        "/workflows/run",
        content=b'{"yaml_definition":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert isinstance(response.json()["detail"], list)


def test_syntactically_malformed_workflow_yaml_uses_compatible_422_envelope(client):
    test_client, _ = client
    response = test_client.post(
        "/workflows/run",
        json={"yaml_definition": "name: broken\nsteps: ["},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert response.json()["detail"].startswith("Invalid YAML:")


def test_api_config_opt_in_runs_independent_steps_concurrently(client, monkeypatch):
    test_client, _ = client
    from workflow_engine import main as main_module

    active = 0
    maximum = 0
    lock = threading.Lock()
    rendezvous = threading.Barrier(2)

    def probe(*, context, params):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            rendezvous.wait(timeout=1)
            return params["step"]
        finally:
            with lock:
                active -= 1

    yaml_definition = """\
name: configured-parallel
steps:
  - id: left
    task: configured_probe
    params: {step: left}
  - id: right
    task: configured_probe
    params: {step: right}
"""
    monkeypatch.setattr(main_module.config, "WORKFLOW_CONCURRENCY_LIMIT", 2)
    monkeypatch.setitem(main_module.TASK_REGISTRY, "configured_probe", probe)

    response = test_client.post(
        "/workflows/run", json={"yaml_definition": yaml_definition}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert maximum == 2


def test_async_api_dispatch_carries_configured_concurrency_limit(client, monkeypatch):
    test_client, _ = client
    from workflow_engine import main as main_module
    from workflow_engine import worker as worker_module

    delayed = MagicMock()
    delayed.id = "task-1"
    delay = MagicMock(return_value=delayed)
    monkeypatch.setattr(main_module.config, "WORKFLOW_CONCURRENCY_LIMIT", 3)
    monkeypatch.setattr(worker_module.run_workflow_task, "delay", delay)

    response = test_client.post(
        "/workflows/run",
        json={"yaml_definition": LINEAR, "async_dispatch": True},
    )

    assert response.status_code == 200
    assert delay.call_args.args[3] == 3


class _FailingStorage:
    def __getattr__(self, _: str):
        raise SQLAlchemyError("database unavailable")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/workflows"),
        ("GET", "/workflows/dead-letters"),
        ("GET", "/workflows/run-1"),
        ("GET", "/workflows/run-1/dag"),
        ("POST", "/workflows/run-1/rerun"),
    ],
)
def test_storage_read_paths_return_compatible_persistence_errors(
    client, monkeypatch, method, path
):
    test_client, _ = client
    from workflow_engine import main as main_module

    monkeypatch.setattr(main_module, "_storage", lambda: _FailingStorage())
    response = test_client.request(method, path, json={} if method == "POST" else None)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_failed"
    assert response.json()["detail"].startswith("Persistence failed:")


@pytest.mark.parametrize(
    ("method", "path", "target", "method_name"),
    [
        ("GET", "/webhooks", "webhooks", "list_triggers"),
        ("POST", "/webhooks/hook", "webhooks", "get"),
        ("GET", "/schedules", "scheduler", "list_schedules"),
        ("DELETE", "/schedules/hourly", "scheduler", "unregister"),
        ("POST", "/schedules/run-due", "scheduler", "dispatch_due"),
    ],
)
def test_runtime_read_paths_return_compatible_persistence_errors(
    client, monkeypatch, method, path, target, method_name
):
    test_client, _ = client
    from workflow_engine import main as main_module

    monkeypatch.setattr(
        getattr(main_module, target),
        method_name,
        MagicMock(side_effect=SQLAlchemyError("database unavailable")),
    )
    response = test_client.request(method, path, json={} if method == "POST" else None)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_failed"
    assert response.json()["detail"].startswith("Persistence failed:")


def test_redis_lock_adapter_uses_vendored_manager_client():
    from workflow_engine.locks import RedisLockProvider

    manager = SimpleNamespace(client=MockRedisClient())
    provider = RedisLockProvider.from_manager(manager)
    with provider.acquire("workflow:one") as acquired:
        assert acquired is True
    assert manager.client.get("workflow:one") is None


def test_redis_lock_adapter_does_not_release_a_reacquired_owner_lock():
    from workflow_engine.locks import RedisLockProvider

    manager = SimpleNamespace(client=MockRedisClient())
    provider = RedisLockProvider.from_manager(manager)
    old_context = provider.acquire("workflow:one")
    assert old_context.__enter__() is True
    old_token = manager.client.get("workflow:one")

    # Model expiry followed by a separate process acquiring the same key.
    manager.client.delete("workflow:one")
    new_context = provider.acquire("workflow:one")
    assert new_context.__enter__() is True
    new_token = manager.client.get("workflow:one")

    assert old_token != new_token
    old_context.__exit__(None, None, None)
    assert manager.client.get("workflow:one") == new_token
    new_context.__exit__(None, None, None)
    assert manager.client.get("workflow:one") is None


def test_workflow_idempotency_persistence_failure_uses_compatible_envelope(
    client, monkeypatch
):
    test_client, services = client

    monkeypatch.setattr(
        services.idempotency,
        "claim",
        MagicMock(side_effect=SQLAlchemyError("database unavailable")),
    )
    response = test_client.post(
        "/workflows/run",
        json={"yaml_definition": LINEAR},
        headers={"Idempotency-Key": "once"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "persistence_failed"
    assert response.json()["detail"].startswith("Persistence failed:")


def test_alembic_upgrade_creates_task3_tables(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'runtime.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    schema = inspect(create_engine(database_url))
    for table in (
        "schedules",
        "webhook_registrations",
        "workflow_definitions",
        "idempotency_records",
        "execution_events",
    ):
        assert table in schema.get_table_names()
    assert "version_hash" in {
        column["name"] for column in schema.get_columns("workflow_runs")
    }
