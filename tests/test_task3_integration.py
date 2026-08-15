"""Task 3 integration contracts for API, durable stores, and eager workers."""

from __future__ import annotations

import hashlib
import hmac
import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import workflow_engine.models as models
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
        with TestClient(main_module.app) as test_client:
            yield test_client, services


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


def test_migration_declares_task3_tables():
    from pathlib import Path

    migration_path = Path("alembic/versions/0002_runtime_persistence.py")
    assert migration_path.exists(), "Task 3 migration is not implemented"
    migration = migration_path.read_text()
    for table in (
        "schedules",
        "webhook_registrations",
        "workflow_definitions",
        "idempotency_records",
        "execution_events",
    ):
        assert f'"{table}"' in migration
