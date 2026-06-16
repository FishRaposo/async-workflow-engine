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


def execute_config(
    config: WorkflowConfig,
    *,
    task_registry: Optional[Dict[str, Any]] = None,
) -> WorkflowExecutor:
    """Execute a parsed config and return the finished executor."""
    executor = WorkflowExecutor(config, task_registry or TASK_REGISTRY)
    executor.execute()
    return executor


def run_workflow(
    yaml_definition: str,
    storage: Any,
    *,
    run_id: Optional[str] = None,
    task_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse, execute, and persist a workflow run; return a result dict.

    Passing ``run_id`` reuses an id (used by rerun to overwrite a prior run).
    """
    config = load_workflow_yaml(yaml_definition)
    executor = execute_config(config, task_registry=task_registry)

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
    return {
        "run_id": saved_id,
        "workflow": config.name,
        "status": executor.overall_status,
        "step_statuses": executor.statuses,
        "results": {k: str(v) for k, v in executor.results.items()},
        "errors": executor.errors,
        "dead_letters": executor.dead_letters,
    }
