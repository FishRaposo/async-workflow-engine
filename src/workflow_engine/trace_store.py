"""Offline-safe execution event persistence adapter."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def event_payload(event: Any) -> Dict[str, Any]:
    """Normalize a TraceContext event or plain mapping for storage and responses."""
    if isinstance(event, dict):
        return dict(event)
    return {
        "sequence": event.sequence,
        "kind": event.kind,
        "trigger_id": event.trigger_id,
        "run_id": event.run_id,
        "step_id": event.step_id,
        "attempt": event.attempt,
        "details": dict(event.details),
    }


class InMemoryExecutionEventStore:
    def __init__(self) -> None:
        self.records: Dict[str, List[Dict[str, Any]]] = {}

    def save(self, run_id: str, events: Iterable[Any]) -> None:
        self.records[run_id] = [event_payload(event) for event in events]

    def list(self, run_id: str) -> List[Dict[str, Any]]:
        return list(self.records.get(run_id, []))
