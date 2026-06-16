"""PostgreSQL-backed workflow run persistence (the default backend).

Wired via ``shared_core.database.DatabaseManager``. The public surface mirrors
:class:`workflow_engine.storage.InMemoryWorkflowStorage` so the API can fall back
to in-memory storage transparently when no database is reachable.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from .models import StepExecution, WorkflowRun


class DatabaseWorkflowStorage:
    """SQLAlchemy-backed run/step persistence."""

    def __init__(self, session_factory: Callable[[], Iterator[Session]]):
        # ``session_factory`` is a generator-style factory (DatabaseManager.get_session)
        self.session_factory = session_factory

    def _session(self) -> Session:
        return next(self.session_factory())

    def save_run(
        self,
        workflow_name: str,
        yaml_definition: str,
        statuses: Dict[str, str],
        results: Optional[Dict[str, Any]] = None,
        *,
        status: str = "completed",
        errors: Optional[Dict[str, str]] = None,
        dead_letters: Optional[List[Dict[str, Any]]] = None,
        task_names: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
    ) -> str:
        run_id = run_id or str(uuid.uuid4())
        errors = errors or {}
        task_names = task_names or {}
        session = self._session()
        try:
            existing = session.get(WorkflowRun, run_id)
            if existing is not None:
                session.delete(existing)
                session.flush()
            now = datetime.now(timezone.utc)
            run = WorkflowRun(
                id=run_id,
                workflow_name=workflow_name,
                yaml_definition=yaml_definition,
                status=status,
                started_at=now,
                completed_at=now,
                dead_letters=list(dead_letters or []),
            )
            session.add(run)
            for step_id, step_status in statuses.items():
                step = StepExecution(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    step_id=step_id,
                    task_name=task_names.get(step_id, ""),
                    status=step_status,
                    result=(
                        str(results.get(step_id))
                        if results and step_id in results
                        else None
                    ),
                    error=errors.get(step_id),
                    attempt=0,
                )
                session.add(step)
            session.commit()
            logger.info(f"Persisted workflow run {run_id}")
            return run_id
        except Exception as exc:
            session.rollback()
            logger.error(f"Failed to persist workflow run: {exc}")
            raise
        finally:
            session.close()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        session = self._session()
        try:
            run = session.get(WorkflowRun, run_id)
            if not run:
                return None
            return {
                "run_id": run.id,
                "workflow_name": run.workflow_name,
                "yaml_definition": run.yaml_definition,
                "status": run.status,
                "step_statuses": {s.step_id: s.status for s in run.steps},
                "results": {s.step_id: s.result for s in run.steps if s.result},
                "errors": {s.step_id: s.error for s in run.steps if s.error},
                "task_names": {
                    s.step_id: s.task_name for s in run.steps if s.task_name
                },
                "dead_letters": run.dead_letters or [],
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": (
                    run.completed_at.isoformat() if run.completed_at else None
                ),
            }
        finally:
            session.close()

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        session = self._session()
        try:
            runs = (
                session.query(WorkflowRun)
                .order_by(WorkflowRun.created_at.desc())
                .limit(limit)
                .all()
            )
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

    def get_dead_letters(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        session = self._session()
        try:
            if run_id is not None:
                run = session.get(WorkflowRun, run_id)
                return list(run.dead_letters or []) if run else []
            runs = (
                session.query(WorkflowRun)
                .filter(WorkflowRun.dead_letters.isnot(None))
                .all()
            )
            out: List[Dict[str, Any]] = []
            for r in runs:
                for dl in r.dead_letters or []:
                    out.append({**dl, "run_id": r.id})
            return out
        finally:
            session.close()
