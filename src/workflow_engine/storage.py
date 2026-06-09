from datetime import datetime, timezone
from typing import Dict, Optional


class InMemoryWorkflowStorage:
    """In-memory storage for persisting run records and task logs."""

    def __init__(self):
        self.records: Dict[str, Dict] = {}

    def save_run(
        self,
        run_id: str,
        workflow_name: str,
        statuses: Dict[str, str],
        results: Optional[Dict[str, str]] = None,
    ):
        self.records[run_id] = {
            "workflow_name": workflow_name,
            "statuses": statuses,
            "results": results or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_run(self, run_id: str) -> Optional[Dict]:
        return self.records.get(run_id)
