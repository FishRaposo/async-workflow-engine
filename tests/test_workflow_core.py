"""Focused contracts for opt-in workflow-owned core capabilities."""

from __future__ import annotations

import hashlib
import hmac
import threading
import time

from workflow_engine.auth import AuthPolicy, LocalRateLimiter, Role
from workflow_engine.config import AppConfig
from workflow_engine.contracts import (
    InMemoryIdempotencyStore,
    TaskInput,
    TaskResult,
    TaskRunner,
)
from workflow_engine.executor import WorkflowExecutor
from workflow_engine.locks import InMemoryLockProvider
from workflow_engine.parser import load_workflow_yaml
from workflow_engine.runner import run_workflow
from workflow_engine.scheduler import InMemoryScheduleStore, WorkflowScheduler
from workflow_engine.storage import InMemoryWorkflowStorage
from workflow_engine.trace import TraceContext
from workflow_engine.versions import InMemoryWorkflowVersionStore
from workflow_engine.webhooks import InMemoryWebhookStore, WebhookRegistry

PARALLEL_YAML = """\
name: parallel
steps:
  - id: left
    task: work
  - id: right
    task: work
  - id: join
    task: work
    depends_on: [left, right]
"""


def test_task_runner_adapts_typed_and_legacy_tasks():
    class Typed:
        def run(self, task_input: TaskInput) -> TaskResult:
            return TaskResult.ok({"typed": task_input.params["value"]})

    runner = TaskRunner(
        {
            "typed": Typed(),
            "legacy": lambda *, context, params: {"legacy": params["value"]},
        }
    )

    assert runner.run("typed", TaskInput(context={}, params={"value": 1})).output == {
        "typed": 1
    }
    assert runner.run("legacy", TaskInput(context={}, params={"value": 2})).output == {
        "legacy": 2
    }


def test_opt_in_typed_io_unwraps_task_result_but_default_keeps_dictionary():
    config = load_workflow_yaml("name: legacy\nsteps:\n  - id: only\n    task: task\n")
    typed_config = load_workflow_yaml(
        "name: typed\ntyped_io: true\nsteps:\n  - id: only\n    task: task\n"
    )
    registry = {"task": lambda *, context, params: TaskResult.ok({"answer": 42})}

    legacy = WorkflowExecutor(config, registry)
    legacy.execute()
    typed = WorkflowExecutor(typed_config, registry)
    typed.execute()
    explicit_typed = WorkflowExecutor(config, registry, typed_io=True)
    explicit_typed.execute()

    assert config.typed_io is False
    assert typed_config.typed_io is True
    assert isinstance(legacy.results["only"], TaskResult)
    assert typed.results["only"] == {"answer": 42}
    assert explicit_typed.results["only"] == {"answer": 42}


def test_parallel_limit_runs_independent_branches_concurrently_and_keeps_join_ordered():
    config = load_workflow_yaml(PARALLEL_YAML)
    started: list[str] = []
    finished: list[str] = []

    def work(*, context, params):
        step_id = "left" if "left" not in context else "right"
        if len(context) == 2:
            step_id = "join"
        started.append(step_id)
        if step_id != "join":
            time.sleep(0.03)
        finished.append(step_id)
        return step_id

    executor = WorkflowExecutor(config, {"work": work}, concurrency_limit=2)
    executor.execute()

    assert executor.statuses == {
        "left": "COMPLETED",
        "right": "COMPLETED",
        "join": "COMPLETED",
    }
    assert finished[-1] == "join"


def test_default_execution_preserves_legacy_yaml_order_after_dependency_resolution():
    config = load_workflow_yaml(
        """\
name: legacy-order
steps:
  - id: A
    task: record
    params: {step_id: A}
  - id: C
    task: record
    depends_on: [A]
    params: {step_id: C}
  - id: B
    task: record
    params: {step_id: B}
"""
    )

    def execute_with(concurrency_limit):
        execution_order: list[str] = []

        def record(*, context, params):
            step_id = params["step_id"]
            execution_order.append(step_id)
            return step_id

        WorkflowExecutor(
            config,
            {"record": record},
            concurrency_limit=concurrency_limit,
        ).execute()
        return execution_order

    assert execute_with(None) == ["A", "C", "B"]
    assert execute_with(1) == ["A", "C", "B"]


def test_trace_records_deterministic_step_retry_and_dlq_events():
    config = load_workflow_yaml(
        "name: trace\nsteps:\n  - id: bad\n    task: fail\n    retries: 1\n"
    )
    trace = TraceContext(trigger_id="trigger-1", run_id="run-1")
    executor = WorkflowExecutor(
        config,
        {"fail": lambda *, context, params: (_ for _ in ()).throw(RuntimeError("bad"))},
        trace=trace,
        sleep_fn=lambda _: None,
    )
    executor.execute()

    assert [(event.kind, event.step_id, event.attempt) for event in trace.events] == [
        ("run.started", None, None),
        ("step.started", "bad", None),
        ("step.retry", "bad", 1),
        ("step.failed", "bad", 2),
        ("dlq.recorded", "bad", 2),
        ("run.finished", None, None),
    ]


def test_retry_trace_attempt_is_the_actual_execution_attempt():
    config = load_workflow_yaml(
        "name: retry-success\nsteps:\n  - id: flaky\n    task: flaky\n    retries: 1\n"
    )
    attempts = 0

    def flaky(*, context, params):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("try again")
        return "ok"

    trace = TraceContext()
    WorkflowExecutor(
        config,
        {"flaky": flaky},
        trace=trace,
        sleep_fn=lambda _: None,
    ).execute()

    assert [(event.kind, event.attempt) for event in trace.events] == [
        ("run.started", None),
        ("step.started", None),
        ("step.retry", 1),
        ("step.completed", 2),
        ("run.finished", None),
    ]


def test_parallel_trace_does_not_label_the_final_failure_as_a_retry():
    config = load_workflow_yaml(
        "name: parallel-failure\nsteps:\n  - id: bad\n    task: fail\n    retries: 1\n"
    )
    trace = TraceContext()
    executor = WorkflowExecutor(
        config,
        {"fail": lambda *, context, params: (_ for _ in ()).throw(RuntimeError("bad"))},
        concurrency_limit=2,
        trace=trace,
        sleep_fn=lambda _: None,
    )

    executor.execute()

    assert [event.attempt for event in trace.events if event.kind == "step.retry"] == [
        1
    ]


def test_in_memory_lock_is_exclusive_and_releases():
    locks = InMemoryLockProvider()
    with locks.acquire("workflow:one") as first:
        assert first is True
        with locks.acquire("workflow:one") as second:
            assert second is False
    with locks.acquire("workflow:one") as after_release:
        assert after_release is True


def test_auth_is_open_by_default_and_enforces_roles_when_enabled():
    policy = AuthPolicy(api_keys={"operator-key": Role.OPERATOR}, required=False)
    assert policy.authorize(None, Role.ADMIN) is True

    secured = AuthPolicy(api_keys={"operator-key": Role.OPERATOR}, required=True)
    assert secured.authorize("operator-key", Role.VIEWER) is True
    assert secured.authorize("operator-key", Role.ADMIN) is False
    assert secured.authorize(None, Role.VIEWER) is False


def test_local_rate_limiter_is_scoped_to_key_or_client():
    limiter = LocalRateLimiter(limit=1, window_seconds=60, recognized_api_keys={"same"})
    assert limiter.allow(api_key="same") is True
    assert limiter.allow(api_key="same") is False
    assert limiter.allow(client_id="other-client") is True


def test_unknown_rate_limit_keys_cannot_create_arbitrary_buckets():
    limiter = LocalRateLimiter(
        limit=1, window_seconds=60, recognized_api_keys={"recognized"}
    )

    assert limiter.allow(api_key="invented-one", client_id="client-a") is True
    assert limiter.allow(api_key="invented-two", client_id="client-a") is False
    assert limiter.allow(client_id="client-b") is True


def test_local_rate_limiter_serializes_concurrent_bucket_updates():
    class CoordinatedBuckets(dict):
        def __init__(self):
            super().__init__()
            self.first_read = threading.Event()
            self.second_read = threading.Event()
            self.reads = 0

        def get(self, key, default=None):
            self.reads += 1
            value = super().get(key, default)
            if self.reads == 1:
                self.first_read.set()
                self.second_read.wait(timeout=0.1)
            elif self.reads == 2:
                self.second_read.set()
            return value

    limiter = LocalRateLimiter(limit=1, window_seconds=60)
    limiter._buckets = CoordinatedBuckets()
    start = threading.Barrier(3)
    results: list[bool] = []

    def attempt():
        start.wait()
        results.append(limiter.allow(client_id="one-client"))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=1)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(results) == [False, True]


def test_webhook_signature_and_idempotency_are_opt_in_contracts():
    store = InMemoryWebhookStore()
    registry = WebhookRegistry(store=store)
    registry.register("signed", "name: wf\nsteps: []\n", secret="top-secret")
    body = b'{"value": 1}'
    signature = "sha256=" + hmac.new(b"top-secret", body, hashlib.sha256).hexdigest()

    assert registry.verify_signature("signed", body, signature) is True
    assert registry.verify_signature("signed", body, "sha256=wrong") is False
    idempotency = InMemoryIdempotencyStore()
    assert idempotency.claim("webhook:signed", "key-1") is True
    assert idempotency.claim("webhook:signed", "key-1") is False


def test_schedule_and_webhook_stores_survive_registry_reconstruction():
    schedule_store = InMemoryScheduleStore()
    scheduler = WorkflowScheduler(store=schedule_store)
    scheduler.register("hourly", "0 * * * *", "name: wf\nsteps: []\n")
    assert (
        WorkflowScheduler(store=schedule_store).list_schedules()[0]["name"] == "hourly"
    )

    webhook_store = InMemoryWebhookStore()
    WebhookRegistry(store=webhook_store).register("hook", "name: wf\nsteps: []\n")
    assert WebhookRegistry(store=webhook_store).get("hook") is not None


def test_legacy_registry_constructor_mappings_remain_compatible():
    from workflow_engine.scheduler import ScheduledWorkflow
    from workflow_engine.webhooks import WebhookTrigger

    schedule = ScheduledWorkflow("hourly", "0 * * * *", "name: wf\nsteps: []\n")
    scheduler = WorkflowScheduler({"hourly": schedule})
    webhooks = WebhookRegistry(
        {"hook": WebhookTrigger("hook", "name: wf\nsteps: []\n")}
    )

    assert scheduler.schedules["hourly"] is schedule
    assert webhooks.get("hook") is not None


def test_content_hash_versions_canonicalize_yaml_and_pin_lookup():
    store = InMemoryWorkflowVersionStore()
    first = store.put("b: 2\na: 1\n")
    second = store.put("a: 1\nb: 2\n")

    assert first.content_hash == second.content_hash
    assert store.get(first.content_hash).yaml_definition == "b: 2\na: 1\n"


def test_runner_pins_a_version_and_can_rerun_the_stored_definition():
    yaml_definition = "name: pinned\nsteps:\n  - id: only\n    task: task\n"
    versions = InMemoryWorkflowVersionStore()
    storage = InMemoryWorkflowStorage()

    first = run_workflow(
        yaml_definition,
        storage,
        task_registry={"task": lambda *, context, params: {"ok": True}},
        version_store=versions,
    )
    rerun = run_workflow(
        "name: ignored\nsteps: []\n",
        storage,
        task_registry={"task": lambda *, context, params: {"ok": True}},
        version_store=versions,
        version_hash=first["version_hash"],
    )

    assert rerun["workflow"] == "pinned"
    assert rerun["version_hash"] == first["version_hash"]


def test_due_schedule_dispatch_uses_opt_in_idempotency_without_celery():
    from datetime import datetime, timedelta, timezone

    scheduler = WorkflowScheduler()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    scheduler.register("minute", "* * * * *", "name: wf\nsteps: []\n", now=now)
    due_at = now + timedelta(minutes=2)
    calls: list[str] = []
    idempotency = InMemoryIdempotencyStore()

    def dispatch(definition):
        calls.append(definition)
        return {"run_id": "run-1"}

    assert scheduler.dispatch_due(dispatch, now=due_at, idempotency=idempotency) == [
        {"name": "minute", "run_id": "run-1"}
    ]
    assert scheduler.dispatch_due(dispatch, now=due_at, idempotency=idempotency) == []
    assert len(calls) == 1


def test_celery_beat_hook_is_off_by_default_and_uses_the_opt_in_registry(monkeypatch):
    from datetime import datetime, timezone

    import workflow_engine.worker as worker

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    worker.beat_scheduler.register(
        "beat-minute", "* * * * *", "name: wf\nsteps: []\n", now=now
    )
    monkeypatch.setenv("WORKFLOW_CELERY_BEAT", "1")
    monkeypatch.setattr(worker, "probe_database", lambda cfg: False)
    result = worker.run_due_schedules.apply().get()

    assert result["dispatched"] == [
        {"name": "beat-minute", "run_id": result["dispatched"][0]["run_id"]}
    ]


def test_new_runtime_capabilities_are_disabled_by_default():
    config = AppConfig()

    assert config.WORKFLOW_AUTH_REQUIRED is False
    assert config.WORKFLOW_CONCURRENCY_LIMIT == 1
    assert config.WORKFLOW_CELERY_BEAT is False
    assert config.WORKFLOW_REDIS_LOCKING_ENABLED is False
