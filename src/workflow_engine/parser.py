"""YAML workflow definition parsing and validation.

A workflow is a name plus a list of steps. Each step names a task from the
registry, an optional list of dependencies, a retry count, an optional
parameter dict passed to the task, and an optional ``condition`` that gates
whether the step runs at all (conditional branching).
"""

from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class WorkflowValidationError(Exception):
    """Raised when a workflow definition has structural issues."""

    def __init__(self, message: str):
        super().__init__(message)


class StepCondition(BaseModel):
    """Conditional gate for a step.

    The step runs only when the result of ``step`` (a prior step's id) satisfies
    the comparison ``equals`` / ``contains`` / ``not_equals`` against ``value``.
    Results are compared as strings, mirroring how the executor stores them.
    """

    step: str
    equals: Optional[str] = None
    not_equals: Optional[str] = None
    contains: Optional[str] = None

    def evaluate(self, results: dict[str, str]) -> bool:
        """Return True if the condition is satisfied given prior step results."""
        if self.step not in results:
            return False
        actual = str(results[self.step])
        if self.equals is not None and actual != self.equals:
            return False
        if self.not_equals is not None and actual == self.not_equals:
            return False
        if self.contains is not None and self.contains not in actual:
            return False
        return True


class StepConfig(BaseModel):
    id: str
    task: str
    depends_on: Optional[List[str]] = Field(default_factory=list)
    retries: int = 3
    params: dict[str, Any] = Field(default_factory=dict)
    condition: Optional[StepCondition] = None

    @field_validator("retries")
    @classmethod
    def _non_negative_retries(cls, value: int) -> int:
        if value < 0:
            raise ValueError("retries must be >= 0")
        return value


class WorkflowConfig(BaseModel):
    name: str
    steps: List[StepConfig]
    schedule: Optional[str] = None  # cron expression for scheduled workflows

    @field_validator("steps")
    @classmethod
    def _unique_step_ids(cls, steps: List[StepConfig]) -> List[StepConfig]:
        seen: set[str] = set()
        for step in steps:
            if step.id in seen:
                raise ValueError(f"Duplicate step id '{step.id}'")
            seen.add(step.id)
        return steps


def detect_cycles(steps: List[StepConfig]) -> None:
    """Validate the DAG: every dependency exists and the graph is acyclic.

    Conditions reference prior step results, so the condition's source step is
    treated as an implicit dependency for cycle/ordering purposes.
    """
    in_degree: dict[str, int] = {s.id: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s.id: [] for s in steps}
    step_ids = set(in_degree)

    for step in steps:
        deps = list(step.depends_on or [])
        if step.condition and step.condition.step not in deps:
            deps.append(step.condition.step)
        for dep in deps:
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
        remaining = sorted(sid for sid, deg in in_degree.items() if deg > 0)
        raise WorkflowValidationError(
            f"Cycle detected in workflow DAG. Unresolved nodes: {remaining}"
        )


def load_workflow_yaml(yaml_content: str) -> WorkflowConfig:
    """Parse YAML text into a validated :class:`WorkflowConfig`."""
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        raise WorkflowValidationError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowValidationError(
            "Workflow definition must be a YAML mapping with 'name' and 'steps'"
        )
    config = WorkflowConfig(**data)
    detect_cycles(config.steps)
    return config
