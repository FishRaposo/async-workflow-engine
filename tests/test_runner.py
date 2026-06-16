"""End-to-end runner tests: parse -> execute -> persist.

Covers the main happy path, conditional branching, the dead-letter queue, and
rerun behaviour against both the in-memory store and a real SQLite-backed store.
"""

import pytest

from workflow_engine.runner import run_workflow
from workflow_engine.storage import InMemoryWorkflowStorage
from workflow_engine.storage_db import DatabaseWorkflowStorage


@pytest.fixture
def memory_storage():
    return InMemoryWorkflowStorage()


@pytest.fixture
def db_storage(mock_db):
    return DatabaseWorkflowStorage(mock_db.get_session)


def test_run_persists_to_memory(memory_storage, branching_yaml, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = run_workflow(branching_yaml, memory_storage)
    assert result["status"] == "completed"
    assert result["step_statuses"]["notify_business"] == "COMPLETED"
    assert result["step_statuses"]["notify_spam"] == "SKIPPED"
    stored = memory_storage.get_run(result["run_id"])
    assert stored is not None
    assert stored["yaml_definition"] == branching_yaml


def test_run_persists_to_database(db_storage, linear_yaml):
    result = run_workflow(linear_yaml, db_storage)
    stored = db_storage.get_run(result["run_id"])
    assert stored["workflow_name"] == "linear"
    assert stored["step_statuses"]["step1"] == "COMPLETED"


def test_dlq_populated_on_failure(memory_storage, dlq_yaml):
    result = run_workflow(dlq_yaml, memory_storage)
    assert result["status"] == "failed"
    assert result["dead_letters"]
    assert result["dead_letters"][0]["step_id"] == "bad"
    dls = memory_storage.get_dead_letters(result["run_id"])
    assert len(dls) == 1


def test_rerun_reuses_run_id(memory_storage, linear_yaml):
    first = run_workflow(linear_yaml, memory_storage)
    second = run_workflow(linear_yaml, memory_storage, run_id=first["run_id"])
    assert second["run_id"] == first["run_id"]
    assert len(memory_storage.list_runs()) == 1


def test_invalid_yaml_raises(memory_storage):
    from workflow_engine.parser import WorkflowValidationError

    with pytest.raises(WorkflowValidationError):
        run_workflow("- not a workflow", memory_storage)
