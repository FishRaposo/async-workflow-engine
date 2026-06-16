import pytest

from workflow_engine.executor import (
    COMPLETED,
    FAILED,
    SKIPPED,
    WorkflowExecutor,
)
from workflow_engine.parser import load_workflow_yaml


def _make_tasks():
    state = {"fails_once": 0}

    def fails_once(context=None, params=None):
        if state["fails_once"] == 0:
            state["fails_once"] += 1
            raise RuntimeError("temporary failure")
        return "recovered"

    def always_fails(context=None, params=None):
        raise RuntimeError("boom")

    def echo_param(context=None, params=None):
        return (params or {}).get("value", "default")

    return {
        "parse_text": lambda context=None, params=None: "parsed",
        "classify_with_llm": lambda context=None, params=None: "classified",
        "send_notification": lambda context=None, params=None: "notified",
        "fails_once": fails_once,
        "always_fails": always_fails,
        "echo_param": echo_param,
    }


def _no_sleep(_seconds):
    return None


LINEAR_YAML = """\
name: linear
steps:
  - id: step1
    task: parse_text
  - id: step2
    task: classify_with_llm
    depends_on: [step1]
"""

FAN_OUT_YAML = """\
name: fan_out
steps:
  - id: root
    task: parse_text
  - id: a
    task: classify_with_llm
    depends_on: [root]
  - id: b
    task: send_notification
    depends_on: [root]
"""

DIAMOND_YAML = """\
name: diamond
steps:
  - id: a
    task: parse_text
  - id: b
    task: classify_with_llm
    depends_on: [a]
  - id: c
    task: send_notification
    depends_on: [a]
  - id: d
    task: parse_text
    depends_on: [b, c]
"""


def test_execute_linear():
    ex = WorkflowExecutor(load_workflow_yaml(LINEAR_YAML), _make_tasks())
    statuses = ex.execute()
    assert statuses["step1"] == COMPLETED
    assert statuses["step2"] == COMPLETED
    assert ex.results["step1"] == "parsed"


def test_execute_fan_out():
    ex = WorkflowExecutor(load_workflow_yaml(FAN_OUT_YAML), _make_tasks())
    statuses = ex.execute()
    assert all(v == COMPLETED for v in statuses.values())


def test_execute_diamond_order():
    ex = WorkflowExecutor(load_workflow_yaml(DIAMOND_YAML), _make_tasks())
    statuses = ex.execute()
    assert statuses["d"] == COMPLETED
    assert ex.overall_status == "completed"


def test_registry_miss_validation():
    ex = WorkflowExecutor(
        load_workflow_yaml("name: x\nsteps:\n  - id: s\n    task: parse_text"),
        {"other": lambda context=None, params=None: "x"},
    )
    with pytest.raises(ValueError, match="Tasks not found in registry"):
        ex.validate_registry()


def test_retry_success():
    cfg = load_workflow_yaml(
        "name: retry\nsteps:\n  - id: s1\n    task: fails_once\n    retries: 2"
    )
    ex = WorkflowExecutor(cfg, _make_tasks(), sleep_fn=_no_sleep)
    statuses = ex.execute()
    assert statuses["s1"] == COMPLETED
    assert ex.retry_counts["s1"] == 1


def test_retry_exhausted_marks_failed():
    cfg = load_workflow_yaml(
        "name: fail\nsteps:\n  - id: s1\n    task: always_fails\n    retries: 1"
    )
    ex = WorkflowExecutor(cfg, _make_tasks(), sleep_fn=_no_sleep)
    statuses = ex.execute()
    assert statuses["s1"] == FAILED
    assert ex.retry_counts["s1"] == 2  # one initial + one retry
    assert "s1" in ex.errors


def test_dead_letter_recorded_on_failure():
    cfg = load_workflow_yaml(
        "name: fail\nsteps:\n  - id: s1\n    task: always_fails\n    retries: 0"
    )
    ex = WorkflowExecutor(cfg, _make_tasks(), sleep_fn=_no_sleep)
    ex.execute()
    assert len(ex.dead_letters) == 1
    dl = ex.dead_letters[0]
    assert dl["step_id"] == "s1"
    assert dl["task"] == "always_fails"
    assert "boom" in dl["error"]


def test_params_forwarded_to_task():
    yaml_str = (
        "name: p\nsteps:\n  - id: s1\n    task: echo_param\n"
        "    params:\n      value: hi"
    )
    ex = WorkflowExecutor(load_workflow_yaml(yaml_str), _make_tasks())
    ex.execute()
    assert ex.results["s1"] == "hi"


def test_conditional_branch_runs_matching():
    yaml_str = """\
name: cond
steps:
  - id: classify
    task: classify_with_llm
  - id: branch
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      equals: classified
"""
    ex = WorkflowExecutor(load_workflow_yaml(yaml_str), _make_tasks())
    statuses = ex.execute()
    assert statuses["branch"] == COMPLETED


def test_conditional_branch_skips_non_matching():
    yaml_str = """\
name: cond
steps:
  - id: classify
    task: classify_with_llm
  - id: branch
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      equals: something_else
"""
    ex = WorkflowExecutor(load_workflow_yaml(yaml_str), _make_tasks())
    statuses = ex.execute()
    assert statuses["branch"] == SKIPPED
    assert ex.overall_status == "completed"


def test_skipped_does_not_deadlock_downstream():
    yaml_str = """\
name: chain
steps:
  - id: a
    task: classify_with_llm
  - id: b
    task: send_notification
    depends_on: [a]
    condition:
      step: a
      equals: never
  - id: c
    task: parse_text
    depends_on: [b]
"""
    ex = WorkflowExecutor(load_workflow_yaml(yaml_str), _make_tasks())
    statuses = ex.execute()
    assert statuses["b"] == SKIPPED
    assert statuses["c"] == COMPLETED


def test_on_step_hook_called_per_step():
    seen = []
    ex = WorkflowExecutor(
        load_workflow_yaml(LINEAR_YAML),
        _make_tasks(),
        on_step=lambda step, status, result, error, attempts: seen.append(
            (step.id, status)
        ),
    )
    ex.execute()
    assert ("step1", COMPLETED) in seen
    assert ("step2", COMPLETED) in seen


def test_overall_status_failed_when_a_step_fails():
    cfg = load_workflow_yaml(
        "name: f\nsteps:\n  - id: s1\n    task: always_fails\n    retries: 0"
    )
    ex = WorkflowExecutor(cfg, _make_tasks(), sleep_fn=_no_sleep)
    ex.execute()
    assert ex.overall_status == "failed"
