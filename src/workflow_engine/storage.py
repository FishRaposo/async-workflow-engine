"""In-memory workflow run storage (no-DB fallback).

This is the fallback backend used when no database is reachable, and the default
in tests and the demo. It mirrors the public surface of
:class:`workflow_engine.storage_db.DatabaseWorkflowStorage` so the API can swap
between them transparently.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class InMemoryWorkflowStorage:
    """Dict-based storage for run records, step logs, and dead letters."""

    def __init__(self) -> None:
        self.records: Dict[str, Dict[str, Any]] = {}

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
        """Persist a run and return its id. ``run_id`` may be supplied for reruns."""
        run_id = run_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self.records[run_id] = {
            "run_id": run_id,
            "workflow_name": workflow_name,
            "yaml_definition": yaml_definition,
            "status": status,
            "step_statuses": dict(statuses),
            "results": {k: str(v) for k, v in (results or {}).items()},
            "errors": dict(errors or {}),
            "dead_letters": list(dead_letters or []),
            "task_names": dict(task_names or {}),
            "created_at": now,
            "completed_at": now,
        }
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.records.get(run_id)

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        runs = sorted(
            self.records.values(),
            key=lambda r: r["created_at"],
            reverse=True,
        )
        return [
            {
                "run_id": r["run_id"],
                "workflow_name": r["workflow_name"],
                "status": r["status"],
                "created_at": r["created_at"],
            }
            for r in runs[:limit]
        ]

    def get_dead_letters(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if run_id is not None:
            record = self.records.get(run_id)
            return list(record["dead_letters"]) if record else []
        out: List[Dict[str, Any]] = []
        for r in self.records.values():
            for dl in r["dead_letters"]:
                out.append({**dl, "run_id": r["run_id"]})
        return out
