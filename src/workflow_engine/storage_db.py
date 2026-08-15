"""PostgreSQL-backed workflow run persistence (the default backend).

Wired via the vendored ``DatabaseManager``. The public surface mirrors
:class:`workflow_engine.storage.InMemoryWorkflowStorage` so the API can fall back
to in-memory storage transparently when no database is reachable.
"""

# SQLAlchemy's legacy Column declarations are retained for compatibility with the
# existing models; pyright cannot infer their runtime instance attribute types.
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    ExecutionEventRecord,
    IdempotencyRecord,
    ScheduleRecord,
    StepExecution,
    WebhookRegistration,
    WorkflowDefinition,
    WorkflowRun,
)
from .scheduler import ScheduledWorkflow
from .trace_store import event_payload
from .versions import WorkflowVersion, canonical_yaml_hash
from .webhooks import WebhookTrigger


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
        version_hash: Optional[str] = None,
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
                version_hash=version_hash,
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
                "version_hash": run.version_hash,
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
                    "run_id": run.id,
                    "workflow_name": run.workflow_name,
                    "status": run.status,
                    "created_at": run.created_at.isoformat()
                    if run.created_at
                    else None,
                }
                for run in runs
            ]
        finally:
            session.close()

    def get_dead_letters(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        session = self._session()
        try:
            if run_id is not None:
                run = session.get(WorkflowRun, run_id)
                return list(run.dead_letters or []) if run else []
            out: List[Dict[str, Any]] = []
            for run in session.query(WorkflowRun).filter(
                WorkflowRun.dead_letters.isnot(None)
            ):
                out.extend(
                    {**letter, "run_id": run.id} for letter in run.dead_letters or []
                )
            return out
        finally:
            session.close()


class _DatabaseStore:
    """Small common session helper for durable Task 3 adapters."""

    def __init__(self, session_factory: Callable[[], Iterator[Session]]):
        self.session_factory = session_factory

    def _session(self) -> Session:
        return next(self.session_factory())


class DatabaseScheduleStore(_DatabaseStore):
    def put(self, schedule: ScheduledWorkflow) -> None:
        session = self._session()
        try:
            record = session.get(ScheduleRecord, schedule.name)
            if record is None:
                record = ScheduleRecord(name=schedule.name)
                session.add(record)
            record.cron = schedule.cron
            record.yaml_definition = schedule.yaml_definition
            record.last_run = schedule.last_run
            record.next_run = schedule.next_run
            record.enabled = schedule.enabled
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _to_schedule(record: ScheduleRecord) -> ScheduledWorkflow:
        def as_utc(value: Optional[datetime]) -> Optional[datetime]:
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        return ScheduledWorkflow(
            name=record.name,
            cron=record.cron,
            yaml_definition=record.yaml_definition,
            last_run=as_utc(record.last_run),
            next_run=as_utc(record.next_run),
            enabled=record.enabled,
        )

    def get(self, name: str) -> Optional[ScheduledWorkflow]:
        session = self._session()
        try:
            record = session.get(ScheduleRecord, name)
            return self._to_schedule(record) if record else None
        finally:
            session.close()

    def delete(self, name: str) -> bool:
        session = self._session()
        try:
            record = session.get(ScheduleRecord, name)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list(self) -> List[ScheduledWorkflow]:
        session = self._session()
        try:
            return [
                self._to_schedule(record) for record in session.query(ScheduleRecord)
            ]
        finally:
            session.close()


class DatabaseWebhookStore(_DatabaseStore):
    def put(self, trigger: WebhookTrigger) -> None:
        session = self._session()
        try:
            record = session.get(WebhookRegistration, trigger.name)
            if record is None:
                record = WebhookRegistration(name=trigger.name)
                session.add(record)
            record.yaml_definition = trigger.yaml_definition
            record.description = trigger.description
            record.secret = trigger.secret
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _to_trigger(record: WebhookRegistration) -> WebhookTrigger:
        return WebhookTrigger(
            record.name, record.yaml_definition, record.description, record.secret
        )

    def get(self, name: str) -> Optional[WebhookTrigger]:
        session = self._session()
        try:
            record = session.get(WebhookRegistration, name)
            return self._to_trigger(record) if record else None
        finally:
            session.close()

    def delete(self, name: str) -> bool:
        session = self._session()
        try:
            record = session.get(WebhookRegistration, name)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list(self) -> List[WebhookTrigger]:
        session = self._session()
        try:
            return [
                self._to_trigger(record)
                for record in session.query(WebhookRegistration)
            ]
        finally:
            session.close()


class DatabaseWorkflowVersionStore(_DatabaseStore):
    def put(self, yaml_definition: str) -> WorkflowVersion:
        content_hash = canonical_yaml_hash(yaml_definition)
        session = self._session()
        try:
            record = session.get(WorkflowDefinition, content_hash)
            if record is None:
                session.add(
                    WorkflowDefinition(
                        content_hash=content_hash, yaml_definition=yaml_definition
                    )
                )
                session.commit()
            return WorkflowVersion(content_hash, yaml_definition)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, content_hash: str) -> Optional[WorkflowVersion]:
        session = self._session()
        try:
            record = session.get(WorkflowDefinition, content_hash)
            return (
                WorkflowVersion(record.content_hash, record.yaml_definition)
                if record
                else None
            )
        finally:
            session.close()


class DatabaseIdempotencyStore(_DatabaseStore):
    def claim(self, namespace: str, key: Optional[str]) -> bool:
        if not key:
            return True
        session = self._session()
        try:
            session.add(IdempotencyRecord(namespace=namespace, key=key))
            session.commit()
            return True
        except IntegrityError:
            session.rollback()
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class DatabaseExecutionEventStore(_DatabaseStore):
    def save(self, run_id: str, events: Any) -> None:
        session = self._session()
        try:
            session.query(ExecutionEventRecord).filter_by(run_id=run_id).delete()
            for event in events:
                payload = event_payload(event)
                session.add(
                    ExecutionEventRecord(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        sequence=payload["sequence"],
                        kind=payload["kind"],
                        trigger_id=payload.get("trigger_id"),
                        step_id=payload.get("step_id"),
                        attempt=payload.get("attempt"),
                        details=payload.get("details", {}),
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list(self, run_id: str) -> List[Dict[str, Any]]:
        session = self._session()
        try:
            records = (
                session.query(ExecutionEventRecord)
                .filter_by(run_id=run_id)
                .order_by(ExecutionEventRecord.sequence)
                .all()
            )
            return [
                {
                    "sequence": record.sequence,
                    "kind": record.kind,
                    "trigger_id": record.trigger_id,
                    "run_id": record.run_id,
                    "step_id": record.step_id,
                    "attempt": record.attempt,
                    "details": record.details or {},
                }
                for record in records
            ]
        finally:
            session.close()
