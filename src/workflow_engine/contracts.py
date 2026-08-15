"""Small compatibility contracts owned by the workflow engine.

These interfaces deliberately describe capabilities instead of choosing a
database, broker, or hosted implementation.  The in-memory implementations are
used by default so importing this module never requires optional infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class WorkflowStorage(Protocol):
    def save_run(
        self,
        workflow_name: str,
        yaml_definition: str,
        statuses: Dict[str, str],
        results: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str: ...

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]: ...


@runtime_checkable
class ScheduleStore(Protocol):
    def put(self, schedule: Any) -> None: ...

    def get(self, name: str) -> Any: ...

    def delete(self, name: str) -> bool: ...

    def list(self) -> list[Any]: ...


@runtime_checkable
class WebhookStore(Protocol):
    def put(self, trigger: Any) -> None: ...

    def get(self, name: str) -> Any: ...

    def delete(self, name: str) -> bool: ...

    def list(self) -> list[Any]: ...


@dataclass(frozen=True)
class TaskInput:
    """Typed input offered to task objects when typed I/O is enabled."""

    context: Dict[str, Any]
    params: Dict[str, Any]


@dataclass(frozen=True)
class TaskResult:
    """Typed task result, without changing legacy dictionary task contracts."""

    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, output: Any, **metadata: Any) -> "TaskResult":
        return cls(output=output, metadata=metadata)

    @classmethod
    def failed(cls, error: str, **metadata: Any) -> "TaskResult":
        return cls(error=error, metadata=metadata)

    def unwrap(self) -> Any:
        if self.error is not None:
            raise RuntimeError(self.error)
        return self.output


@runtime_checkable
class TypedTask(Protocol):
    def run(self, task_input: TaskInput) -> TaskResult: ...


class TaskRunner:
    """Adapt typed task objects and established keyword-callable tasks."""

    def __init__(self, registry: Dict[str, Any]):
        self.registry = registry

    def run(self, name: str, task_input: TaskInput) -> TaskResult:
        task = self.registry[name]
        if isinstance(task, TypedTask):
            result = task.run(task_input)
        else:
            result = task(context=task_input.context, params=task_input.params)
        return result if isinstance(result, TaskResult) else TaskResult.ok(result)


class InMemoryIdempotencyStore:
    """Atomic process-local claim store for opt-in trigger deduplication."""

    def __init__(self) -> None:
        self._claims: set[tuple[str, str]] = set()
        self._lock = Lock()

    def claim(self, namespace: str, key: Optional[str]) -> bool:
        if not key:
            return True
        claim = (namespace, key)
        with self._lock:
            if claim in self._claims:
                return False
            self._claims.add(claim)
            return True
