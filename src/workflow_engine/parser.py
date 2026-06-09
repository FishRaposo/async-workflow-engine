from typing import List, Optional

import yaml
from pydantic import BaseModel, Field


class WorkflowValidationError(Exception):
    """Raised when a workflow definition has structural issues."""

    def __init__(self, message: str):
        super().__init__(message)


class StepConfig(BaseModel):
    id: str
    task: str
    depends_on: Optional[List[str]] = Field(default_factory=list)
    retries: int = 3


class WorkflowConfig(BaseModel):
    name: str
    steps: List[StepConfig]


def detect_cycles(steps: List[StepConfig]) -> None:
    in_degree: dict[str, int] = {s.id: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s.id: [] for s in steps}
    step_ids = set(in_degree)

    for step in steps:
        for dep in step.depends_on or []:
            if dep not in step_ids:
                raise WorkflowValidationError(
                    f"Step '{step.id}' depends on unknown step '{dep}'"
                )
            adjacency[dep].append(step.id)
            in_degree[step.id] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0

    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(steps):
        remaining = sorted(set(in_degree) - {s.id for s in steps if s.id})
        raise WorkflowValidationError(
            f"Cycle detected in workflow DAG. Unresolved nodes: {remaining}"
        )


def load_workflow_yaml(yaml_content: str) -> WorkflowConfig:
    data = yaml.safe_load(yaml_content)
    config = WorkflowConfig(**data)
    detect_cycles(config.steps)
    return config
