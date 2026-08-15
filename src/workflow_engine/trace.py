"""Deterministic, in-process execution event collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ExecutionEvent:
    sequence: int
    kind: str
    trigger_id: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    attempt: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceContext:
    """Ordered event sink; no clocks are included, keeping traces reproducible."""

    trigger_id: Optional[str] = None
    run_id: Optional[str] = None
    events: list[ExecutionEvent] = field(default_factory=list)

    def emit(
        self,
        kind: str,
        *,
        step_id: Optional[str] = None,
        attempt: Optional[int] = None,
        **details: Any,
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            sequence=len(self.events) + 1,
            kind=kind,
            trigger_id=self.trigger_id,
            run_id=self.run_id,
            step_id=step_id,
            attempt=attempt,
            details=details,
        )
        self.events.append(event)
        return event
