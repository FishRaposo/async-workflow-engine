"""Generate deterministic, offline portfolio evidence from real engine services."""

# ruff: noqa: E402

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

# Settings are intentionally pinned before any workflow-engine import.  The demo
# never needs hosted services, credentials, or a broker.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WORKFLOW_ASYNC"] = "0"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from workflow_engine.auth import AuthPolicy, LocalRateLimiter, Role
from workflow_engine.contracts import InMemoryIdempotencyStore, TaskInput, TaskResult
from workflow_engine.executor import WorkflowExecutor
from workflow_engine.models import Base
from workflow_engine.parser import WorkflowValidationError, load_workflow_yaml
from workflow_engine.runner import run_workflow
from workflow_engine.runtime import RuntimeServices
from workflow_engine.storage import InMemoryWorkflowStorage
from workflow_engine.storage_db import DatabaseWorkflowStorage
from workflow_engine.tasks import TASK_REGISTRY, classify_with_llm, parse_text
from workflow_engine.trace import TraceContext
from workflow_engine.webhooks import WebhookRegistry

BRANCHING_YAML = """\
name: evidence-branching
steps:
  - id: parse
    task: parse_text
    params:
      text: "business request from ACME"
  - id: classify
    task: classify_with_llm
    depends_on: [parse]
    params:
      labels: [business, spam]
      text: "business request from ACME"
  - id: notify_business
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: business
  - id: notify_spam
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: spam
"""

FAILURE_YAML = """\
name: evidence-failure
steps:
  - id: parse
    task: parse_text
  - id: fail
    task: always_fail
    depends_on: [parse]
    retries: 1
    params:
      message: "intentional evidence failure"
"""

PARALLEL_YAML = """\
name: evidence-parallel
steps:
  - id: first
    task: probe
  - id: second
    task: probe
"""

TYPED_YAML = """\
name: evidence-typed
steps:
  - id: typed
    task: typed_probe
    params:
      proof: TaskInput->TaskResult
"""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sqlite_storage() -> DatabaseWorkflowStorage:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def session_factory() -> Iterator[Session]:
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    return DatabaseWorkflowStorage(session_factory)


def _validation_evidence() -> dict[str, bool]:
    valid = load_workflow_yaml(BRANCHING_YAML).name == "evidence-branching"
    try:
        load_workflow_yaml(
            "name: cycle\nsteps:\n"
            "  - id: one\n    task: parse_text\n    depends_on: [two]\n"
            "  - id: two\n    task: parse_text\n    depends_on: [one]\n"
        )
    except WorkflowValidationError:
        cycle_refused = True
    else:  # pragma: no cover - makes a broken parser visible in evidence
        cycle_refused = False
    try:
        WorkflowExecutor(
            load_workflow_yaml(
                "name: unknown\nsteps:\n  - id: only\n    task: absent\n"
            ),
            TASK_REGISTRY,
        ).execute()
    except ValueError:
        unknown_task_refused = True
    else:  # pragma: no cover - makes a broken executor visible in evidence
        unknown_task_refused = False
    return {
        "valid_yaml": valid,
        "cycle_refused": cycle_refused,
        "unknown_task_refused": unknown_task_refused,
    }


def _execution_evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    storage = InMemoryWorkflowStorage()
    branch = run_workflow(
        BRANCHING_YAML,
        storage,
        run_id="normalized-branch-run",
        concurrency_limit=2,
        trace=TraceContext(trigger_id="normalized-trigger"),
    )
    failure_trace = TraceContext(trigger_id="normalized-trigger")
    failure = run_workflow(
        FAILURE_YAML,
        storage,
        run_id="normalized-failure-run",
        trace=failure_trace,
    )
    rerun = run_workflow(
        FAILURE_YAML,
        storage,
        run_id="normalized-failure-run",
        trace=TraceContext(trigger_id="normalized-trigger"),
    )
    active = 0
    maximum = 0
    lock = threading.Lock()
    rendezvous = threading.Barrier(2)

    def probe(*, context: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            rendezvous.wait(timeout=2)
            return parse_text(context=context, params={"text": "parallel evidence"})
        finally:
            with lock:
                active -= 1

    parallel = WorkflowExecutor(
        load_workflow_yaml(PARALLEL_YAML), {"probe": probe}, concurrency_limit=2
    )
    parallel.execute()

    class TypedProbe:
        def run(self, task_input: TaskInput) -> TaskResult:
            return TaskResult.ok(
                {"kind": "typed", "params": task_input.params},
                adapter="TaskInput->TaskResult",
            )

    typed = WorkflowExecutor(
        load_workflow_yaml(TYPED_YAML), {"typed_probe": TypedProbe()}, typed_io=True
    )
    typed.execute()
    observed_backoffs: list[float] = []
    backoff_trace = TraceContext(trigger_id="normalized-trigger")
    backoff_executor = WorkflowExecutor(
        load_workflow_yaml(FAILURE_YAML),
        TASK_REGISTRY,
        sleep_fn=observed_backoffs.append,
        trace=backoff_trace,
    )
    backoff_executor.execute()
    return (
        {
            "branch_statuses": branch["step_statuses"],
            "typed_io": typed.results["typed"],
            "trace_kinds": [event["kind"] for event in branch["events"]],
            "bounded_parallel": {
                "limit": 2,
                "observed_max": maximum,
                "statuses": parallel.statuses,
            },
            "partial_failure_status": failure["status"],
            "partial_failure_step_statuses": failure["step_statuses"],
            "partial_failure_trace": [
                {"kind": event.kind, "attempt": event.attempt}
                for event in failure_trace.events
            ],
            "dlq_attempts": failure["dead_letters"][0]["attempts"],
            "retry_backoff": {
                "observed_seconds": observed_backoffs,
                "retry_events": [
                    {"kind": event.kind, "attempt": event.attempt}
                    for event in backoff_trace.events
                    if event.kind == "step.retry"
                ],
            },
            "rerun_preserved_id": rerun["run_id"] == failure["run_id"],
        },
        branch,
    )


def _runtime_evidence() -> dict[str, Any]:
    memory = InMemoryWorkflowStorage()
    sqlite = _sqlite_storage()
    memory_run = run_workflow(BRANCHING_YAML, memory, run_id="memory-run")
    sqlite_run = run_workflow(BRANCHING_YAML, sqlite, run_id="sqlite-run")
    services = RuntimeServices.in_memory()
    fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    schedule = services.scheduler.register(
        "evidence-schedule", "* * * * *", BRANCHING_YAML, now=fixed_now
    )
    schedule.next_run = fixed_now - timedelta(minutes=1)
    services.scheduler.store.put(schedule)
    dispatched = services.scheduler.dispatch_due(
        lambda yaml_definition: run_workflow(
            yaml_definition, memory, run_id="scheduled-run"
        ),
        now=fixed_now,
        idempotency=services.idempotency,
    )
    schedule.next_run = fixed_now - timedelta(minutes=1)
    services.scheduler.store.put(schedule)
    duplicate_dispatched = services.scheduler.dispatch_due(
        lambda yaml_definition: run_workflow(
            yaml_definition, memory, run_id="duplicate-scheduled-run"
        ),
        now=fixed_now,
        idempotency=services.idempotency,
    )
    return {
        "in_memory_round_trip": memory.get_run(memory_run["run_id"]) is not None,
        "sqlite_round_trip": sqlite.get_run(sqlite_run["run_id"]) is not None,
        "schedule_due_dispatch": [item["name"] for item in dispatched],
        "schedule_duplicate_dispatch": [item["name"] for item in duplicate_dispatched],
    }


def _security_evidence() -> dict[str, Any]:
    webhooks = WebhookRegistry()
    webhooks.register("evidence-hook", BRANCHING_YAML, secret="normalized-secret")
    body = b'{"event":"evidence"}'
    valid_signature = (
        "sha256=" + hmac.new(b"normalized-secret", body, hashlib.sha256).hexdigest()
    )
    policy = AuthPolicy(api_keys={"normalized-key": Role.OPERATOR}, required=True)
    limiter = LocalRateLimiter(limit=2, window_seconds=3600)
    idempotency = InMemoryIdempotencyStore()
    return {
        "webhook_hmac": {
            "valid": webhooks.verify_signature("evidence-hook", body, valid_signature),
            "invalid": webhooks.verify_signature("evidence-hook", body, "sha256=bad"),
        },
        "idempotency": [
            idempotency.claim("evidence", "one"),
            idempotency.claim("evidence", "one"),
        ],
        "auth": {
            "operator_allowed": policy.authorize("normalized-key", Role.OPERATOR),
            "viewer_refused": policy.authorize(None, Role.VIEWER),
        },
        "rate_limit": [limiter.allow(client_id="evidence") for _ in range(3)],
    }


def _evidence() -> dict[str, Any]:
    execution, branch = _execution_evidence()
    return {
        "schema_version": 1,
        "environment": {
            "database": "sqlite-memory",
            "network": "disabled",
            "credentials": "redacted",
            "provider_output": "deterministic-simulation",
            "timestamps": "normalized",
            "durations": "normalized",
            "paths": "normalized",
            "ids": "normalized",
        },
        "validation": _validation_evidence(),
        "execution": execution,
        "runtime": _runtime_evidence(),
        "security": _security_evidence(),
        "tasks": {
            "text_parsing": parse_text(params={"text": "deterministic parsed input"}),
            "simulated_classification": classify_with_llm(
                params={"text": "business request", "labels": ["business", "spam"]}
            ),
        },
        "dashboard_fixture": {
            "run_id": "normalized-branch-run",
            "status": branch["status"],
            "step_statuses": branch["step_statuses"],
            "events": branch["events"],
            "dead_letters": branch["dead_letters"],
        },
    }


def _markdown(evidence: dict[str, Any], reproducibility_hash: str) -> str:
    branch_statuses = {
        step_id: evidence["execution"]["branch_statuses"][step_id]
        for step_id in sorted(evidence["execution"]["branch_statuses"])
    }
    return "\n".join(
        [
            "# Async Workflow Engine evidence",
            "",
            f"Reproducibility hash: `{reproducibility_hash}`",
            "",
            "- Offline SQLite and in-memory storage exercised.",
            "- Validation, execution, runtime, security, tasks, and dashboard fixtures "
            "are recorded.",
            f"- Branch result: `{branch_statuses}`.",
            "",
        ]
    )


def generate_evidence(output_dir: str | Path) -> dict[str, Any]:
    """Write a closed evidence directory and return its deterministic manifest."""
    directory = Path(output_dir)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    evidence = _evidence()
    reproducibility_hash = hashlib.sha256(_canonical(evidence)).hexdigest()
    manifest = {
        "artifact_files": ["evidence.json", "manifest.json", "report.md"],
        "reproducibility_hash": reproducibility_hash,
        "schema_version": 1,
    }
    (directory / "evidence.json").write_bytes(_canonical(evidence) + b"\n")
    (directory / "manifest.json").write_bytes(_canonical(manifest) + b"\n")
    (directory / "report.md").write_text(
        _markdown(evidence, reproducibility_hash), encoding="utf-8"
    )
    checksums = "\n".join(
        f"{_sha256(directory / filename)}  {filename}"
        for filename in ("evidence.json", "manifest.json", "report.md")
    )
    (directory / "checksums.sha256").write_text(checksums + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":  # pragma: no cover - command line convenience
    destination = ROOT / "artifacts" / "portfolio" / "async-workflow-engine-evidence"
    print(json.dumps(generate_evidence(destination), indent=2, sort_keys=True))
