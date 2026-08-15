"""Run orchestration: parse → execute → persist.

A single ``run_workflow`` entry point shared by the synchronous API path and the
Celery worker. It parses the YAML, runs the :class:`WorkflowExecutor`, and
persists the result (run record, per-step statuses, errors, and the dead-letter
queue) through whichever storage backend is active.
"""

from typing import Any, Dict, Optional

from loguru import logger

from .executor import WorkflowExecutor
from .parser import WorkflowConfig, load_workflow_yaml
from .tasks import TASK_REGISTRY
from .trace import TraceContext
from .versions import WorkflowVersionStore


def execute_config(
    config: WorkflowConfig,
    *,
    task_registry: Optional[Dict[str, Any]] = None,
    concurrency_limit: Optional[int] = None,
    typed_io: bool = False,
    trace: Optional[TraceContext] = None,
) -> WorkflowExecutor:
    """Execute a parsed config and return the finished executor."""
    executor = WorkflowExecutor(
        config,
        task_registry or TASK_REGISTRY,
        concurrency_limit=concurrency_limit,
        typed_io=typed_io,
        trace=trace,
    )
    executor.execute()
    return executor


def run_workflow(
    yaml_definition: str,
    storage: Any,
    *,
    run_id: Optional[str] = None,
    task_registry: Optional[Dict[str, Any]] = None,
    concurrency_limit: Optional[int] = None,
    typed_io: bool = False,
    trace: Optional[TraceContext] = None,
    version_store: Optional[WorkflowVersionStore] = None,
    version_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse, execute, and persist a workflow run; return a result dict.

    Passing ``run_id`` reuses an id (used by rerun to overwrite a prior run).
    """
    if version_hash is not None:
        if version_store is None:
            raise ValueError("version_hash requires a workflow version store")
        version = version_store.get(version_hash)
        if version is None:
            raise ValueError(f"Workflow version '{version_hash}' not found")
        yaml_definition = version.yaml_definition
    version = version_store.put(yaml_definition) if version_store is not None else None
    if trace is not None:
        trace.emit("trigger.received")
    config = load_workflow_yaml(yaml_definition)
    executor = execute_config(
        config,
        task_registry=task_registry,
        concurrency_limit=concurrency_limit,
        typed_io=typed_io,
        trace=trace,
    )

    task_names = {step.id: step.task for step in config.steps}
    saved_id = storage.save_run(
        config.name,
        yaml_definition,
        executor.statuses,
        executor.results,
        status=executor.overall_status,
        errors=executor.errors,
        dead_letters=executor.dead_letters,
        task_names=task_names,
        run_id=run_id,
    )
    logger.info(
        f"Workflow '{config.name}' run {saved_id} finished: {executor.overall_status}"
    )
    result = {
        "run_id": saved_id,
        "workflow": config.name,
        "status": executor.overall_status,
        "step_statuses": executor.statuses,
        "results": {k: str(v) for k, v in executor.results.items()},
        "errors": executor.errors,
        "dead_letters": executor.dead_letters,
    }
    if version is not None:
        result["version_hash"] = version.content_hash
    return result
