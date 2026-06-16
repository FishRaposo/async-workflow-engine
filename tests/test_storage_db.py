"""DatabaseWorkflowStorage tests against a real in-memory SQLite DB.

Uses ``shared_core.testing.MockDatabase`` so the full SQLAlchemy persistence
path (insert, query, relationship loading, JSON column) is exercised without a
real PostgreSQL server.
"""

import uuid

import pytest

from workflow_engine.storage_db import DatabaseWorkflowStorage


@pytest.fixture
def storage(mock_db):
    return DatabaseWorkflowStorage(mock_db.get_session)


def test_save_run_returns_uuid(storage):
    run_id = storage.save_run("wf", "name: wf\nsteps: []", {"step1": "COMPLETED"})
    uuid.UUID(run_id)  # raises if not a valid uuid


def test_save_and_get_roundtrip(storage):
    run_id = storage.save_run(
        "wf",
        "name: wf\nsteps: []",
        {"a": "COMPLETED", "b": "SKIPPED"},
        results={"a": "out"},
        errors={},
        task_names={"a": "parse_text", "b": "send_notification"},
    )
    record = storage.get_run(run_id)
    assert record["workflow_name"] == "wf"
    assert record["step_statuses"] == {"a": "COMPLETED", "b": "SKIPPED"}
    assert record["results"]["a"] == "out"
    assert record["status"] == "completed"


def test_get_run_missing_returns_none(storage):
    assert storage.get_run("does-not-exist") is None


def test_get_run_includes_task_names(storage):
    # Regression: DatabaseWorkflowStorage.get_run() must return ``task_names``
    # (keyed by step_id) so its shape matches InMemoryWorkflowStorage.
    run_id = storage.save_run(
        "wf",
        "yaml",
        {"a": "COMPLETED", "b": "SKIPPED"},
        task_names={"a": "parse_text", "b": "send_notification"},
    )
    record = storage.get_run(run_id)
    assert "task_names" in record
    assert record["task_names"] == {"a": "parse_text", "b": "send_notification"}


def test_dead_letters_persisted_as_json(storage):
    run_id = storage.save_run(
        "wf",
        "yaml",
        {"bad": "FAILED"},
        status="failed",
        errors={"bad": "boom"},
        dead_letters=[{"step_id": "bad", "task": "always_fail", "error": "boom"}],
    )
    record = storage.get_run(run_id)
    assert record["status"] == "failed"
    assert record["errors"]["bad"] == "boom"
    dls = storage.get_dead_letters(run_id)
    assert len(dls) == 1
    assert dls[0]["step_id"] == "bad"


def test_global_dead_letters(storage):
    storage.save_run(
        "wf",
        "yaml",
        {"bad": "FAILED"},
        status="failed",
        dead_letters=[{"step_id": "bad", "task": "t", "error": "x"}],
    )
    storage.save_run("clean", "yaml", {"ok": "COMPLETED"})
    dls = storage.get_dead_letters()
    assert len(dls) == 1
    assert "run_id" in dls[0]


def test_list_runs(storage):
    storage.save_run("a", "yaml", {"s": "COMPLETED"})
    storage.save_run("b", "yaml", {"s": "COMPLETED"})
    runs = storage.list_runs()
    assert len(runs) == 2
    assert {r["workflow_name"] for r in runs} == {"a", "b"}


def test_rerun_overwrites_same_run_id(storage):
    run_id = storage.save_run("wf", "yaml", {"s": "COMPLETED"})
    storage.save_run("wf", "yaml", {"s": "FAILED"}, status="failed", run_id=run_id)
    record = storage.get_run(run_id)
    assert record["status"] == "failed"
    assert record["step_statuses"]["s"] == "FAILED"
    # No duplicate steps left behind.
    assert list(record["step_statuses"].keys()) == ["s"]
