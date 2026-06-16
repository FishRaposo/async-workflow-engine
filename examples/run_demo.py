"""End-to-end demo of the async workflow engine — runs fully offline.

Demonstrates: YAML parsing, DAG execution with conditional branching, the
dead-letter queue on a failing step, run persistence (in-memory fallback when no
database is present), the DAG projection a UI would render, and cron scheduling.
No API keys, no database, no broker required.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from workflow_engine.dag import build_dag
from workflow_engine.parser import load_workflow_yaml
from workflow_engine.runner import run_workflow
from workflow_engine.scheduler import WorkflowScheduler
from workflow_engine.storage import InMemoryWorkflowStorage

BRANCHING_WORKFLOW = """
name: lead_intake
steps:
  - id: parse_input
    task: parse_text
    params:
      text: "ACME Corp requests a business quote for 500 widgets."
  - id: classify
    task: classify_with_llm
    depends_on: [parse_input]
    params:
      labels: [business, support, spam]
      text: "ACME Corp requests a business quote for 500 widgets."
  - id: notify_sales
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: business
    params:
      channel: slack
      message: "New business lead routed to sales."
  - id: quarantine
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: spam
"""

DLQ_WORKFLOW = """
name: flaky_pipeline
steps:
  - id: ingest
    task: parse_text
  - id: risky
    task: always_fail
    depends_on: [ingest]
    retries: 1
"""


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> None:
    storage = InMemoryWorkflowStorage()

    section("1. Conditional branching workflow")
    result = run_workflow(BRANCHING_WORKFLOW, storage)
    print(f"Run id     : {result['run_id']}")
    print(f"Status     : {result['status']}")
    print(f"Step states: {result['step_statuses']}")
    assert result["step_statuses"]["notify_sales"] == "COMPLETED"
    assert result["step_statuses"]["quarantine"] == "SKIPPED"

    section("2. DAG projection (what a dashboard would render)")
    config = load_workflow_yaml(BRANCHING_WORKFLOW)
    dag = build_dag(config, result["step_statuses"])
    for node in dag["nodes"]:
        print(f"  node {node['id']:<14} [{node['status']}]")
    for edge in dag["edges"]:
        print(f"  edge {edge['from']} -> {edge['to']} ({edge['type']})")

    section("3. Dead-letter queue on a failing step")
    dlq_result = run_workflow(DLQ_WORKFLOW, storage)
    print(f"Status     : {dlq_result['status']}")
    print(f"Step states: {dlq_result['step_statuses']}")
    print(f"Dead letters: {dlq_result['dead_letters']}")
    assert dlq_result["status"] == "failed"
    assert dlq_result["dead_letters"], "expected a dead letter for the failing step"

    section("4. Persistence + manual rerun (in-memory fallback)")
    print(f"Runs stored: {[r['run_id'][:8] for r in storage.list_runs()]}")
    rerun = run_workflow(BRANCHING_WORKFLOW, storage, run_id=result["run_id"])
    print(f"Reran run {rerun['run_id'][:8]} -> {rerun['status']}")
    assert rerun["run_id"] == result["run_id"]

    section("5. Cron scheduler")
    scheduler = WorkflowScheduler()
    sched = scheduler.register("nightly_intake", "0 2 * * *", BRANCHING_WORKFLOW)
    print(f"Scheduled '{sched.name}' ({sched.cron}) — next run: {sched.next_run}")

    section("Demo complete — all assertions passed")


if __name__ == "__main__":
    main()
