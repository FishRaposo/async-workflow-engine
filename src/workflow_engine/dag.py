"""DAG graph projection for UI consumption.

Turns a parsed :class:`WorkflowConfig` (plus optional per-step statuses) into a
``{nodes, edges}`` structure a dashboard can render directly. Dependency edges
are solid; conditional edges are flagged so a UI can style them differently.
"""

from typing import Any, Dict, List, Optional

from .parser import WorkflowConfig


def build_dag(
    config: WorkflowConfig, statuses: Optional[Dict[str, str]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Return ``{"nodes": [...], "edges": [...]}`` for the workflow DAG."""
    statuses = statuses or {}
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for step in config.steps:
        nodes.append(
            {
                "id": step.id,
                "task": step.task,
                "status": statuses.get(step.id, "PENDING"),
                "conditional": step.condition is not None,
                "retries": step.retries,
            }
        )
        for dep in step.depends_on or []:
            edges.append({"from": dep, "to": step.id, "type": "dependency"})
        if step.condition is not None:
            edges.append(
                {
                    "from": step.condition.step,
                    "to": step.id,
                    "type": "conditional",
                }
            )

    return {"nodes": nodes, "edges": edges}
