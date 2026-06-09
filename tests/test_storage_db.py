import uuid
from unittest.mock import MagicMock

import pytest
from workflow_engine.models import StepExecution, WorkflowRun
from workflow_engine.storage_db import DatabaseWorkflowStorage


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.get.return_value = None
    session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    def factory():
        yield mock_session

    return factory


@pytest.fixture
def storage(mock_session_factory):
    return DatabaseWorkflowStorage(mock_session_factory)


class TestDatabaseWorkflowStorage:
    def test_save_run_returns_uuid(self, storage):
        run_id = storage.save_run(
            "test_workflow",
            "name: test\nsteps: []",
            {"step1": "COMPLETED"},
        )
        assert isinstance(run_id, str)
        uuid.UUID(run_id)

    def test_save_run_rolls_back_on_error(self, storage, mock_session):
        mock_session.commit.side_effect = Exception("DB error")
        with pytest.raises(Exception, match="DB error"):
            storage.save_run(
                "test_workflow",
                "name: test\nsteps: []",
                {"step1": "COMPLETED"},
            )
        mock_session.rollback.assert_called_once()

    def test_save_run_passes_results(self, storage):
        run_id = storage.save_run(
            "test_workflow",
            "name: test\nsteps: [{- id: s1\n  task: t}]",
            {"s1": "COMPLETED"},
            results={"s1": "output_value"},
        )
        assert run_id is not None

    def test_get_run_returns_none_for_missing(self, storage, mock_session):
        mock_session.get.return_value = None
        result = storage.get_run("nonexistent")
        assert result is None

    def test_get_run_returns_dict_for_existing(self, storage, mock_session):
        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.workflow_name = "test_workflow"
        mock_run.status = "completed"
        mock_run.created_at = MagicMock()
        mock_run.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_run.completed_at = MagicMock()
        mock_run.completed_at.isoformat.return_value = "2026-01-01T00:01:00"
        mock_step = MagicMock()
        mock_step.step_id = "step1"
        mock_step.status = "COMPLETED"
        mock_run.steps = [mock_step]
        mock_session.get.return_value = mock_run

        result = storage.get_run("run-123")
        assert result is not None
        assert result["run_id"] == "run-123"
        assert result["workflow_name"] == "test_workflow"
        assert result["step_statuses"]["step1"] == "COMPLETED"

    def test_list_runs_returns_list(self, storage, mock_session):
        mock_run = MagicMock()
        mock_run.id = "run-1"
        mock_run.workflow_name = "wf1"
        mock_run.status = "completed"
        mock_run.created_at = MagicMock()
        mock_run.created_at.isoformat.return_value = "2026-01-01T00:00:00"
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_run
        ]

        runs = storage.list_runs()
        assert len(runs) == 1
        assert runs[0]["workflow_name"] == "wf1"

    def test_list_runs_empty(self, storage, mock_session):
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        runs = storage.list_runs()
        assert runs == []
