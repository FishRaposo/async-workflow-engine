import pytest

from workflow_engine.executor import WorkflowExecutor
from workflow_engine.parser import load_workflow_yaml

TASKS = {
    "parse_text": lambda context=None: "parsed",
    "classify_with_llm": lambda context=None: "classified",
    "send_notification": lambda context=None: "notified",
    "fails_once": lambda context=None: _fails_once(),
    "always_fails": lambda context=None: (_ for _ in ()).throw(Exception("boom")),
}


def _make_fails_once():
    counter = [0]

    def inner():
        if counter[0] == 0:
            counter[0] += 1
            raise Exception("temporary failure")
        return "recovered"

    return inner


_fails_once = _make_fails_once()


LINEAR_YAML = """\
name: linear
steps:
  - id: step1
    task: parse_text
  - id: step2
    task: classify_with_llm
    depends_on:
      - step1
"""

FAN_OUT_YAML = """\
name: fan_out
steps:
  - id: root
    task: parse_text
  - id: a
    task: classify_with_llm
    depends_on:
      - root
  - id: b
    task: send_notification
    depends_on:
      - root
"""

SINGLE_STEP_YAML = """\
name: single
steps:
  - id: only
    task: parse_text
"""


def test_execute_linear():
    cfg = load_workflow_yaml(LINEAR_YAML)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["step1"] == "COMPLETED"
    assert statuses["step2"] == "COMPLETED"
    assert ex.results["step1"] == "parsed"
    assert ex.results["step2"] == "classified"


def test_execute_fan_out():
    cfg = load_workflow_yaml(FAN_OUT_YAML)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["root"] == "COMPLETED"
    assert statuses["a"] == "COMPLETED"
    assert statuses["b"] == "COMPLETED"


def test_execute_single_step():
    cfg = load_workflow_yaml(SINGLE_STEP_YAML)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["only"] == "COMPLETED"


def test_registry_miss_validation():
    cfg = load_workflow_yaml(SINGLE_STEP_YAML)
    ex = WorkflowExecutor(cfg, {"other": lambda context=None: "x"})
    with pytest.raises(ValueError, match="Tasks not found in registry"):
        ex.validate_registry()


def test_retry_success():
    yaml_str = "name: retry\nsteps:\n  - id: s1\n    task: fails_once\n    retries: 2"
    cfg = load_workflow_yaml(yaml_str)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["s1"] == "COMPLETED"
    assert ex.retry_counts["s1"] == 1


def test_retry_exhausted():
    yaml_str = "name: fail\nsteps:\n  - id: s1\n    task: always_fails\n    retries: 1"
    cfg = load_workflow_yaml(yaml_str)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["s1"] == "FAILED"


def test_context_passing():
    yaml_str = """\
name: ctx
steps:
  - id: a
    task: parse_text
  - id: b
    task: classify_with_llm
    depends_on:
      - a
"""
    cfg = load_workflow_yaml(yaml_str)
    ex = WorkflowExecutor(cfg, TASKS)
    statuses = ex.execute()
    assert statuses["a"] == "COMPLETED"
    assert statuses["b"] == "COMPLETED"
