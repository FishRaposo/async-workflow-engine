import pytest

from workflow_engine.parser import (
    StepCondition,
    WorkflowValidationError,
    load_workflow_yaml,
)

VALID_LINEAR = """\
name: linear_workflow
steps:
  - id: step1
    task: parse_text
  - id: step2
    task: classify_with_llm
    depends_on:
      - step1
"""

VALID_DIAMOND = """\
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

CYCLE_YAML = """\
name: cyclic
steps:
  - id: step1
    task: parse_text
    depends_on: [step2]
  - id: step2
    task: classify_with_llm
    depends_on: [step1]
"""

UNKNOWN_DEP_YAML = """\
name: unknown_dep
steps:
  - id: step1
    task: parse_text
    depends_on: [nonexistent]
"""

CONDITION_YAML = """\
name: conditional
steps:
  - id: classify
    task: classify_with_llm
  - id: branch
    task: send_notification
    condition:
      step: classify
      contains: business
"""


def test_load_valid_linear():
    cfg = load_workflow_yaml(VALID_LINEAR)
    assert cfg.name == "linear_workflow"
    assert len(cfg.steps) == 2
    assert cfg.steps[1].depends_on == ["step1"]


def test_load_valid_diamond():
    cfg = load_workflow_yaml(VALID_DIAMOND)
    assert len(cfg.steps) == 4
    assert cfg.steps[3].depends_on == ["b", "c"]


def test_default_retries():
    cfg = load_workflow_yaml(VALID_LINEAR)
    assert cfg.steps[0].retries == 3


def test_custom_retries():
    cfg = load_workflow_yaml(
        "name: r\nsteps:\n  - id: s1\n    task: parse_text\n    retries: 5"
    )
    assert cfg.steps[0].retries == 5


def test_negative_retries_rejected():
    with pytest.raises((ValueError, Exception)):
        load_workflow_yaml(
            "name: r\nsteps:\n  - id: s1\n    task: parse_text\n    retries: -1"
        )


def test_params_parsed():
    cfg = load_workflow_yaml(
        "name: p\nsteps:\n  - id: s1\n    task: parse_text\n    params:\n      text: hi"
    )
    assert cfg.steps[0].params == {"text": "hi"}


def test_condition_parsed():
    cfg = load_workflow_yaml(CONDITION_YAML)
    cond = cfg.steps[1].condition
    assert cond is not None
    assert cond.step == "classify"
    assert cond.contains == "business"


def test_schedule_parsed():
    cfg = load_workflow_yaml(VALID_LINEAR + "schedule: '* * * * *'\n")
    assert cfg.schedule == "* * * * *"


def test_cycle_detection():
    with pytest.raises(WorkflowValidationError, match="Cycle detected"):
        load_workflow_yaml(CYCLE_YAML)


def test_unknown_dependency():
    with pytest.raises(WorkflowValidationError, match="depends on unknown step"):
        load_workflow_yaml(UNKNOWN_DEP_YAML)


def test_condition_unknown_step_rejected():
    bad = """\
name: bad
steps:
  - id: s1
    task: parse_text
    condition:
      step: ghost
      equals: x
"""
    with pytest.raises(WorkflowValidationError, match="unknown step"):
        load_workflow_yaml(bad)


def test_duplicate_step_ids_rejected():
    dup = """\
name: dup
steps:
  - id: s1
    task: parse_text
  - id: s1
    task: parse_text
"""
    with pytest.raises((ValueError, Exception)):
        load_workflow_yaml(dup)


def test_invalid_yaml():
    with pytest.raises(WorkflowValidationError):
        load_workflow_yaml(": invalid: yaml: :")


def test_non_mapping_yaml():
    with pytest.raises(WorkflowValidationError):
        load_workflow_yaml("- just\n- a\n- list")


def test_missing_name():
    with pytest.raises((ValueError, Exception)):
        load_workflow_yaml("steps:\n  - id: s1\n    task: parse_text\n")


def test_empty_steps():
    cfg = load_workflow_yaml("name: empty\nsteps: []\n")
    assert len(cfg.steps) == 0


class TestStepCondition:
    def test_equals_true(self):
        cond = StepCondition(step="a", equals="business")
        assert cond.evaluate({"a": "business"}) is True

    def test_equals_false(self):
        cond = StepCondition(step="a", equals="business")
        assert cond.evaluate({"a": "spam"}) is False

    def test_contains(self):
        cond = StepCondition(step="a", contains="usi")
        assert cond.evaluate({"a": "business"}) is True
        assert cond.evaluate({"a": "spam"}) is False

    def test_not_equals(self):
        cond = StepCondition(step="a", not_equals="spam")
        assert cond.evaluate({"a": "business"}) is True
        assert cond.evaluate({"a": "spam"}) is False

    def test_missing_source_is_false(self):
        cond = StepCondition(step="a", equals="x")
        assert cond.evaluate({}) is False
