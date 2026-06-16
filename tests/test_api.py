"""API tests — every endpoint, success and error paths.

Storage is patched to a single shared in-memory backend so runs persist across
requests within a test. Redis/DB health are mocked; no network or real DB.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

LINEAR_YAML = "name: test_flow\nsteps:\n  - id: step1\n    task: parse_text\n"

CYCLE_YAML = """\
name: cycle
steps:
  - id: a
    task: parse_text
    depends_on: [b]
  - id: b
    task: parse_text
    depends_on: [a]
"""

DLQ_YAML = """\
name: dlq
steps:
  - id: ok
    task: parse_text
  - id: bad
    task: always_fail
    depends_on: [ok]
    retries: 0
"""


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("WORKFLOW_ASYNC", raising=False)

    from workflow_engine import main as main_module
    from workflow_engine.storage import InMemoryWorkflowStorage

    shared_storage = InMemoryWorkflowStorage()
    # Fresh scheduler/webhook registries per test.
    from workflow_engine.scheduler import WorkflowScheduler
    from workflow_engine.webhooks import WebhookRegistry

    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with (
        patch.object(main_module, "_storage", lambda: shared_storage),
        patch.object(main_module, "db_manager", mock_db),
        patch.object(main_module, "redis_manager", mock_redis),
        patch.object(main_module, "scheduler", WorkflowScheduler()),
        patch.object(main_module, "webhooks", WebhookRegistry()),
        patch.object(main_module, "probe_database", lambda cfg=None: False),
        patch("workflow_engine.db.probe_database", lambda cfg=None: False),
    ):
        with TestClient(main_module.app) as c:
            yield c, shared_storage


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #
def test_validate_valid(client):
    c, _ = client
    resp = c.post("/workflows/validate", json={"yaml_definition": LINEAR_YAML})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_validate_cycle_returns_422(client):
    c, _ = client
    resp = c.post("/workflows/validate", json={"yaml_definition": CYCLE_YAML})
    assert resp.status_code == 422


def test_validate_unknown_task_returns_422(client):
    c, _ = client
    bad = "name: x\nsteps:\n  - id: s\n    task: nonexistent_task\n"
    resp = c.post("/workflows/validate", json={"yaml_definition": bad})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# run / get / list / dag
# --------------------------------------------------------------------------- #
def test_run_workflow_success(client):
    c, _ = client
    resp = c.post("/workflows/run", json={"yaml_definition": LINEAR_YAML})
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow"] == "test_flow"
    assert data["step_statuses"]["step1"] == "COMPLETED"
    assert data["dispatched"] == "sync"
    assert "run_id" in data


def test_run_workflow_invalid_yaml_returns_422(client):
    c, _ = client
    resp = c.post("/workflows/run", json={"yaml_definition": "- not a workflow"})
    assert resp.status_code == 422


def test_get_run_after_run(client):
    c, _ = client
    run_id = c.post("/workflows/run", json={"yaml_definition": LINEAR_YAML}).json()[
        "run_id"
    ]
    resp = c.get(f"/workflows/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["workflow_name"] == "test_flow"


def test_get_run_not_found(client):
    c, _ = client
    resp = c.get("/workflows/missing-id")
    assert resp.status_code == 404


def test_list_workflows(client):
    c, _ = client
    c.post("/workflows/run", json={"yaml_definition": LINEAR_YAML})
    resp = c.get("/workflows")
    assert resp.status_code == 200
    assert len(resp.json()["runs"]) == 1


def test_get_dag(client):
    c, _ = client
    run_id = c.post("/workflows/run", json={"yaml_definition": LINEAR_YAML}).json()[
        "run_id"
    ]
    resp = c.get(f"/workflows/{run_id}/dag")
    assert resp.status_code == 200
    dag = resp.json()
    assert {n["id"] for n in dag["nodes"]} == {"step1"}
    assert "edges" in dag


def test_get_dag_not_found(client):
    c, _ = client
    resp = c.get("/workflows/missing/dag")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# rerun
# --------------------------------------------------------------------------- #
def test_rerun_workflow(client):
    c, _ = client
    run_id = c.post("/workflows/run", json={"yaml_definition": LINEAR_YAML}).json()[
        "run_id"
    ]
    resp = c.post(f"/workflows/{run_id}/rerun", json={})
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id


def test_rerun_missing_run_returns_404(client):
    c, _ = client
    resp = c.post("/workflows/nope/rerun", json={})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# dead-letters
# --------------------------------------------------------------------------- #
def test_dead_letters_after_failed_run(client):
    c, _ = client
    c.post("/workflows/run", json={"yaml_definition": DLQ_YAML})
    resp = c.get("/workflows/dead-letters")
    assert resp.status_code == 200
    dls = resp.json()["dead_letters"]
    assert any(d["step_id"] == "bad" for d in dls)


# --------------------------------------------------------------------------- #
# webhooks
# --------------------------------------------------------------------------- #
def test_register_and_trigger_webhook(client):
    c, _ = client
    reg = c.post(
        "/webhooks/lead/register",
        json={"yaml_definition": LINEAR_YAML, "description": "lead hook"},
    )
    assert reg.status_code == 200
    listed = c.get("/webhooks").json()["webhooks"]
    assert any(w["name"] == "lead" for w in listed)
    trig = c.post("/webhooks/lead", json={})
    assert trig.status_code == 200
    assert trig.json()["triggered"] == "lead"
    assert trig.json()["step_statuses"]["step1"] == "COMPLETED"


def test_trigger_unregistered_webhook_returns_404(client):
    c, _ = client
    resp = c.post("/webhooks/ghost", json={})
    assert resp.status_code == 404


def test_register_webhook_invalid_yaml_returns_422(client):
    c, _ = client
    resp = c.post(
        "/webhooks/bad/register", json={"yaml_definition": "- nope", "description": ""}
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# schedules
# --------------------------------------------------------------------------- #
def test_create_list_delete_schedule(client):
    c, _ = client
    resp = c.post(
        "/schedules",
        json={"name": "nightly", "cron": "0 2 * * *", "yaml_definition": LINEAR_YAML},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "nightly"
    listed = c.get("/schedules").json()["schedules"]
    assert any(s["name"] == "nightly" for s in listed)
    delete = c.delete("/schedules/nightly")
    assert delete.status_code == 200


def test_create_schedule_invalid_cron_returns_422(client):
    c, _ = client
    resp = c.post(
        "/schedules",
        json={"name": "bad", "cron": "not-cron", "yaml_definition": LINEAR_YAML},
    )
    assert resp.status_code == 422


def test_delete_missing_schedule_returns_404(client):
    c, _ = client
    resp = c.delete("/schedules/ghost")
    assert resp.status_code == 404


def test_run_due_schedules(client):
    c, _ = client
    # Register a schedule that is already due (cron every minute) and tick it.
    c.post(
        "/schedules",
        json={"name": "everymin", "cron": "* * * * *", "yaml_definition": LINEAR_YAML},
    )
    # next_run is in the future by construction; run-due returns empty but 200.
    resp = c.post("/schedules/run-due")
    assert resp.status_code == 200
    assert "dispatched" in resp.json()


# --------------------------------------------------------------------------- #
# tasks / health
# --------------------------------------------------------------------------- #
def test_list_tasks(client):
    c, _ = client
    resp = c.get("/tasks")
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["tasks"]]
    assert "parse_text" in names
    assert "classify_with_llm" in names


def test_health(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "async-workflow-engine"
    assert "dependencies" in body
    assert "storage" in body
