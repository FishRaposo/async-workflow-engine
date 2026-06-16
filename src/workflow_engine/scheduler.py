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
from typing import Dict, List, Optional

from loguru import logger

try:
    from croniter import croniter

    _HAS_CRONITER = True
except ImportError:  # pragma: no cover - croniter is a declared dependency
    croniter = None  # type: ignore
    _HAS_CRONITER = False


def is_valid_cron(expression: str) -> bool:
    """Return True if ``expression`` is a valid cron expression."""
    if not _HAS_CRONITER:
        # Minimal structural fallback: 5 whitespace-separated fields.
        return len(expression.split()) == 5
    return bool(croniter.is_valid(expression))


def next_run_time(expression: str, after: Optional[datetime] = None) -> datetime:
    """Compute the next fire time for a cron expression after ``after``."""
    base = after or datetime.now(timezone.utc)
    if not _HAS_CRONITER:  # pragma: no cover - dependency present in CI
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
class WorkflowScheduler:
    """Registry of cron-scheduled workflows."""

    schedules: Dict[str, ScheduledWorkflow] = field(default_factory=dict)

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
        self.schedules[name] = sched
        logger.info(f"Registered schedule '{name}' ({cron}) — next: {sched.next_run}")
        return sched

    def unregister(self, name: str) -> bool:
        return self.schedules.pop(name, None) is not None

    def list_schedules(self) -> List[Dict]:
        return [
            {
                "name": s.name,
                "cron": s.cron,
                "enabled": s.enabled,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "next_run": s.next_run.isoformat() if s.next_run else None,
            }
            for s in self.schedules.values()
        ]

    def due(self, now: Optional[datetime] = None) -> List[ScheduledWorkflow]:
        """Return enabled schedules whose ``next_run`` is at or before ``now``."""
        now = now or datetime.now(timezone.utc)
        ready = [
            s
            for s in self.schedules.values()
            if s.enabled and s.next_run is not None and s.next_run <= now
        ]
        return ready

    def mark_ran(self, name: str, now: Optional[datetime] = None) -> None:
        """Advance a schedule after it has fired."""
        now = now or datetime.now(timezone.utc)
        sched = self.schedules.get(name)
        if not sched:
            return
        sched.last_run = now
        if _HAS_CRONITER:
            sched.next_run = next_run_time(sched.cron, now)
