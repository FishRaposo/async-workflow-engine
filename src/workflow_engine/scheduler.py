"""Cron-style workflow scheduler.

Registers named workflows with a cron expression and computes which are due.
Backed by ``croniter`` for real cron parsing; the scheduler itself is pure and
deterministic (it takes the ``now`` to evaluate against), so it tests with no
clock dependency and no background threads.

In production this would be driven by Celery beat or an APScheduler loop calling
:meth:`WorkflowScheduler.due` on a tick; here it is exposed via the API so a
dashboard can list schedules and trigger due runs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from .contracts import InMemoryIdempotencyStore, ScheduleStore

try:
    from croniter import croniter

    _HAS_CRONITER = True
except ImportError:  # pragma: no cover - croniter is a declared dependency
    croniter = None  # type: ignore
    _HAS_CRONITER = False


def is_valid_cron(expression: str) -> bool:
    """Return True if ``expression`` is a valid cron expression."""
    if croniter is None:
        # Minimal structural fallback: 5 whitespace-separated fields.
        return len(expression.split()) == 5
    return bool(croniter.is_valid(expression))


def next_run_time(expression: str, after: Optional[datetime] = None) -> datetime:
    """Compute the next fire time for a cron expression after ``after``."""
    base = after or datetime.now(timezone.utc)
    if croniter is None:  # pragma: no cover - dependency present in CI
        raise RuntimeError("croniter is required to compute next run times")
    return croniter(expression, base).get_next(datetime)


@dataclass
class ScheduledWorkflow:
    name: str
    cron: str
    yaml_definition: str
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True


@dataclass
class InMemoryScheduleStore:
    """Process-local registry store used unless a persistence adapter is supplied."""

    records: Dict[str, ScheduledWorkflow] = field(default_factory=dict)

    def put(self, schedule: ScheduledWorkflow) -> None:
        self.records[schedule.name] = schedule

    def get(self, name: str) -> Optional[ScheduledWorkflow]:
        return self.records.get(name)

    def delete(self, name: str) -> bool:
        return self.records.pop(name, None) is not None

    def list(self) -> List[ScheduledWorkflow]:
        return list(self.records.values())


@dataclass(init=False)
class WorkflowScheduler:
    """Registry of cron-scheduled workflows."""

    store: ScheduleStore

    def __init__(
        self,
        schedules: Optional[Dict[str, ScheduledWorkflow]] = None,
        *,
        store: Optional[ScheduleStore] = None,
    ) -> None:
        """Accept the legacy mapping while allowing a workflow-owned store."""
        self.store = store or InMemoryScheduleStore()
        for schedule in (schedules or {}).values():
            self.store.put(schedule)

    @property
    def schedules(self) -> Dict[str, ScheduledWorkflow]:
        """Legacy mapping view retained for callers that inspect schedules."""
        records = getattr(self.store, "records", None)
        if records is None:
            return {schedule.name: schedule for schedule in self.store.list()}
        return records

    def register(
        self,
        name: str,
        cron: str,
        yaml_definition: str,
        *,
        now: Optional[datetime] = None,
    ) -> ScheduledWorkflow:
        if not is_valid_cron(cron):
            raise ValueError(f"Invalid cron expression: {cron!r}")
        now = now or datetime.now(timezone.utc)
        sched = ScheduledWorkflow(
            name=name,
            cron=cron,
            yaml_definition=yaml_definition,
            next_run=next_run_time(cron, now) if _HAS_CRONITER else None,
        )
        self.store.put(sched)
        logger.info(f"Registered schedule '{name}' ({cron}) — next: {sched.next_run}")
        return sched

    def unregister(self, name: str) -> bool:
        return self.store.delete(name)

    def list_schedules(self) -> List[Dict]:
        return [
            {
                "name": s.name,
                "cron": s.cron,
                "enabled": s.enabled,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "next_run": s.next_run.isoformat() if s.next_run else None,
            }
            for s in self.store.list()
        ]

    def due(self, now: Optional[datetime] = None) -> List[ScheduledWorkflow]:
        """Return enabled schedules whose ``next_run`` is at or before ``now``."""
        now = now or datetime.now(timezone.utc)
        ready = [
            s
            for s in self.store.list()
            if s.enabled and s.next_run is not None and s.next_run <= now
        ]
        return ready

    def mark_ran(self, name: str, now: Optional[datetime] = None) -> None:
        """Advance a schedule after it has fired."""
        now = now or datetime.now(timezone.utc)
        sched = self.store.get(name)
        if not sched:
            return
        sched.last_run = now
        if _HAS_CRONITER:
            sched.next_run = next_run_time(sched.cron, now)
        self.store.put(sched)

    def dispatch_due(
        self,
        dispatch: Callable[[str], Dict[str, Any]],
        *,
        now: Optional[datetime] = None,
        idempotency: Optional[InMemoryIdempotencyStore] = None,
    ) -> List[Dict[str, Any]]:
        """Dispatch due workflows once per scheduled fire time.

        A Celery-beat process can call this method, but it is equally usable from
        a local/manual tick and does not import Celery.
        """
        dispatched: List[Dict[str, Any]] = []
        for sched in self.due(now=now):
            fire_time = sched.next_run.isoformat() if sched.next_run else "unscheduled"
            if idempotency and not idempotency.claim(
                f"schedule:{sched.name}", fire_time
            ):
                continue
            result = dispatch(sched.yaml_definition)
            self.mark_ran(sched.name, now=now)
            dispatched.append({"name": sched.name, "run_id": result.get("run_id")})
        return dispatched
