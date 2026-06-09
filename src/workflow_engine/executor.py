import time
from typing import Dict

from loguru import logger

from .parser import StepConfig, WorkflowConfig


class WorkflowExecutor:
    """Orchestrates the execution of steps in a validated DAG."""

    def __init__(
        self,
        config: WorkflowConfig,
        task_registry: Dict,
    ):
        self.config = config
        self.task_registry = task_registry
        self.statuses: Dict[str, str] = {step.id: "PENDING" for step in config.steps}
        self.results: Dict[str, str] = {}
        self.retry_counts: Dict[str, int] = {step.id: 0 for step in config.steps}

    def validate_registry(self) -> None:
        missing = [
            step.task
            for step in self.config.steps
            if step.task not in self.task_registry
        ]
        if missing:
            raise ValueError(
                f"Tasks not found in registry: {', '.join(sorted(missing))}"
            )

    def execute(self) -> Dict[str, str]:
        logger.info(f"Starting execution for workflow: {self.config.name}")
        self.validate_registry()
        completed = set()

        while len(completed) < len(self.config.steps):
            executed_this_round = False
            for step in self.config.steps:
                if self.statuses[step.id] != "PENDING":
                    continue

                deps_met = all(dep in completed for dep in (step.depends_on or []))
                if not deps_met:
                    continue

                logger.info(f"Running step {step.id} (Task: {step.task})...")
                self.statuses[step.id] = "RUNNING"

                task_fn = self.task_registry.get(step.task)
                context = dict(self.results)
                success = self._run_with_retry(step, task_fn, context)
                if success:
                    completed.add(step.id)
                    executed_this_round = True

            if not executed_this_round and len(completed) < len(self.config.steps):
                logger.error("Deadlock detected or dependency loop in DAG execution.")
                break

        return self.statuses

    def _run_with_retry(
        self, step: StepConfig, task_fn, context: Dict[str, str]
    ) -> bool:
        max_retries = step.retries
        for attempt in range(max_retries + 1):
            try:
                res = task_fn(context=context)
                self.results[step.id] = str(res)
                self.statuses[step.id] = "COMPLETED"
                if attempt > 0:
                    logger.info(f"Step {step.id} succeeded on retry {attempt}")
                return True
            except Exception as e:
                self.retry_counts[step.id] = attempt + 1
                if attempt < max_retries:
                    backoff = 0.5 * (2**attempt)
                    msg = (
                        f"Step {step.id} failed "
                        f"(attempt {attempt + 1}/{max_retries + 1}): "
                        f"{e}. Retrying in {backoff:.1f}s..."
                    )
                    logger.warning(msg)
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"Step {step.id} failed after {max_retries + 1} attempts: {e}"
                    )
                    self.statuses[step.id] = "FAILED"
                    return False
        return False
