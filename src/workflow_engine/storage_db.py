import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from loguru import logger
from sqlalchemy.orm import Session

from .models import StepExecution, WorkflowRun


class DatabaseWorkflowStorage:
    """PostgreSQL-backed workflow run persistence."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def save_run(
        self,
        workflow_name: str,
        yaml_definition: str,
        statuses: Dict[str, str],
        results: Optional[Dict[str, str]] = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        session: Session = next(self.session_factory())
        try:
            run = WorkflowRun(
                id=run_id,
                workflow_name=workflow_name,
                yaml_definition=yaml_definition,
                status="completed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            session.add(run)
            for step_id, status in statuses.items():
                step = StepExecution(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    step_id=step_id,
                    task_name="",
                    status=status,
                    result=results.get(step_id) if results else None,
                )
                session.add(step)
            session.commit()
            logger.info(f"Persisted workflow run {run_id}")
            return run_id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to persist workflow run: {e}")
            raise
        finally:
            session.close()

    def get_run(self, run_id: str) -> Optional[Dict]:
        session: Session = next(self.session_factory())
        try:
            run = session.get(WorkflowRun, run_id)
            if not run:
                return None
            return {
                "run_id": run.id,
                "workflow_name": run.workflow_name,
                "status": run.status,
                "step_statuses": {
                    s.step_id: s.status for s in run.steps
                },
                "created_at": (
                    run.created_at.isoformat() if run.created_at else None
                ),
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
            }
        finally:
            session.close()

    def list_runs(self) -> list[Dict]:
        session: Session = next(self.session_factory())
        try:
            runs = session.query(WorkflowRun).order_by(
                WorkflowRun.created_at.desc()
            ).limit(50).all()
            return [
                {
                    "run_id": r.id,
                    "workflow_name": r.workflow_name,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ]
        finally:
            session.close()
