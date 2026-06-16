"""DAG execution engine.

``WorkflowExecutor`` resolves step dependencies in topological order and runs
each step's registered task. It supports:

* **Retry with exponential backoff** (per-step ``retries``).
* **Conditional branching** — a step with a ``condition`` runs only when a prior
  step's result satisfies it; otherwise the step is ``SKIPPED`` and counts as
  resolved so downstream steps are not deadlocked.
* **Parameter passing** — each step's ``params`` are forwarded to the task, and
  prior step results are forwarded as ``context``.
* **A dead-letter queue (DLQ)** — every step that exhausts its retries is
  recorded with its error for later inspection or rerun.
* **A per-step hook** — ``on_step`` is invoked after each step resolves, used by
  the API/worker to persist incremental progress.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from .parser import StepConfig, WorkflowConfig

# Step status constants
PENDING = "PENDING"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"

StepHook = Callable[[StepConfig, str, Any, Optional[str], int], None]


class WorkflowExecutor:
    """Orchestrates the execution of steps in a validated DAG."""

    def __init__(
        self,
        config: WorkflowConfig,
        task_registry: Dict[str, Any],
        *,
        on_step: Optional[StepHook] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        max_backoff: float = 8.0,
    ):
        self.config = config
        self.task_registry = task_registry
        self.statuses: Dict[str, str] = {step.id: PENDING for step in config.steps}
        self.results: Dict[str, Any] = {}
        self.retry_counts: Dict[str, int] = {step.id: 0 for step in config.steps}
        self.errors: Dict[str, str] = {}
        self.dead_letters: List[Dict[str, Any]] = []
        self.on_step = on_step
        self._sleep = sleep_fn
        self._max_backoff = max_backoff

    def validate_registry(self) -> None:
        missing = [
            step.task
            for step in self.config.steps
            if step.task not in self.task_registry
        ]
        if missing:
            raise ValueError(
                f"Tasks not found in registry: {', '.join(sorted(set(missing)))}"
            )

    def execute(self) -> Dict[str, str]:
        logger.info(f"Starting execution for workflow: {self.config.name}")
        self.validate_registry()
        resolved: set[str] = set()
        total = len(self.config.steps)

        while len(resolved) < total:
            executed_this_round = False
            for step in self.config.steps:
                if self.statuses[step.id] != PENDING:
                    continue

                deps_met = all(dep in resolved for dep in (step.depends_on or []))
                if not deps_met:
                    continue

                # Conditional branching: the condition's source step must already
                # be resolved (guaranteed by detect_cycles' implicit dependency).
                if step.condition is not None:
                    cond_src = step.condition.step
                    if cond_src not in resolved:
                        continue
                    if not step.condition.evaluate(self.results):
                        self.statuses[step.id] = SKIPPED
                        resolved.add(step.id)
                        executed_this_round = True
                        logger.info(f"Step {step.id} SKIPPED (condition not met)")
                        self._emit(step)
                        continue

                self._run_step(step)
                resolved.add(step.id)
                executed_this_round = True

            if not executed_this_round and len(resolved) < total:
                logger.error("Deadlock detected or dependency loop in DAG execution.")
                break

        return self.statuses

    def _run_step(self, step: StepConfig) -> None:
        logger.info(f"Running step {step.id} (task: {step.task})...")
        self.statuses[step.id] = RUNNING
        task_fn = self.task_registry.get(step.task)
        context = dict(self.results)
        self._run_with_retry(step, task_fn, context)
        self._emit(step)

    def _emit(self, step: StepConfig) -> None:
        if self.on_step is None:
            return
        try:
            self.on_step(
                step,
                self.statuses[step.id],
                self.results.get(step.id),
                self.errors.get(step.id),
                self.retry_counts[step.id],
            )
        except Exception as exc:  # pragma: no cover - hook must never break a run
            logger.warning(f"on_step hook failed for {step.id}: {exc}")

    def _run_with_retry(
        self, step: StepConfig, task_fn: Callable, context: Dict[str, Any]
    ) -> bool:
        max_retries = step.retries
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                res = task_fn(context=context, params=step.params)
                self.results[step.id] = res
                self.statuses[step.id] = COMPLETED
                if attempt > 0:
                    logger.info(f"Step {step.id} succeeded on retry {attempt}")
                return True
            except Exception as exc:
                last_error = str(exc)
                self.retry_counts[step.id] = attempt + 1
                if attempt < max_retries:
                    backoff = min(0.5 * (2**attempt), self._max_backoff)
                    logger.warning(
                        f"Step {step.id} failed "
                        f"(attempt {attempt + 1}/{max_retries + 1}): {exc}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    self._sleep(backoff)
                else:
                    logger.error(
                        f"Step {step.id} failed after {max_retries + 1} attempts: {exc}"
                    )
        self.statuses[step.id] = FAILED
        self.errors[step.id] = last_error
        self.dead_letters.append(
            {
                "step_id": step.id,
                "task": step.task,
                "error": last_error,
                "attempts": self.retry_counts[step.id],
                "params": dict(step.params),
            }
        )
        return False

    @property
    def overall_status(self) -> str:
        """Aggregate run status from per-step statuses."""
        values = set(self.statuses.values())
        if FAILED in values:
            return "failed"
        if values <= {COMPLETED, SKIPPED}:
            return "completed"
        return "partial"
