from workflow_engine.models import StepExecution, WorkflowRun


class TestWorkflowRunModel:
    def test_tablename(self):
        assert WorkflowRun.__tablename__ == "workflow_runs"

    def test_columns_present(self):
        assert hasattr(WorkflowRun, "workflow_name")
        assert hasattr(WorkflowRun, "yaml_definition")
        assert hasattr(WorkflowRun, "status")
        assert hasattr(WorkflowRun, "started_at")
        assert hasattr(WorkflowRun, "completed_at")
        assert hasattr(WorkflowRun, "id")
        assert hasattr(WorkflowRun, "created_at")
        assert hasattr(WorkflowRun, "updated_at")

    def test_steps_relationship_exists(self):
        assert hasattr(WorkflowRun, "steps")

    def test_status_default(self):
        col = WorkflowRun.__table__.columns["status"]
        assert col.default.arg == "pending"


class TestStepExecutionModel:
    def test_tablename(self):
        assert StepExecution.__tablename__ == "step_executions"

    def test_columns_present(self):
        assert hasattr(StepExecution, "run_id")
        assert hasattr(StepExecution, "step_id")
        assert hasattr(StepExecution, "task_name")
        assert hasattr(StepExecution, "status")
        assert hasattr(StepExecution, "result")
        assert hasattr(StepExecution, "error")
        assert hasattr(StepExecution, "attempt")
        assert hasattr(StepExecution, "id")
        assert hasattr(StepExecution, "created_at")
        assert hasattr(StepExecution, "updated_at")

    def test_status_default(self):
        col = StepExecution.__table__.columns["status"]
        assert col.default.arg == "PENDING"

    def test_run_relationship_exists(self):
        assert hasattr(StepExecution, "run")

    def test_run_id_is_foreign_key(self):
        col = StepExecution.__table__.columns["run_id"]
        assert col.foreign_keys
