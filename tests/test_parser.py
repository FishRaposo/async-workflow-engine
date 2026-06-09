import pytest

from workflow_engine.parser import (
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

VALID_FAN_OUT = """\
name: fan_out
steps:
  - id: root
    task: parse_text
  - id: child_a
    task: classify_with_llm
    depends_on:
      - root
  - id: child_b
    task: send_notification
    depends_on:
      - root
"""

VALID_DIAMOND = """\
name: diamond
steps:
  - id: a
    task: parse_text
  - id: b
    task: classify_with_llm
    depends_on:
      - a
  - id: c
    task: send_notification
    depends_on:
      - a
  - id: d
    task: parse_text
    depends_on:
      - b
      - c
"""

CYCLE_YAML = """\
name: cyclic
steps:
  - id: step1
    task: parse_text
    depends_on:
      - step2
  - id: step2
    task: classify_with_llm
    depends_on:
      - step1
"""

UNKNOWN_DEP_YAML = """\
name: unknown_dep
steps:
  - id: step1
    task: parse_text
    depends_on:
      - nonexistent
"""


def test_load_valid_linear():
    cfg = load_workflow_yaml(VALID_LINEAR)
    assert cfg.name == "linear_workflow"
    assert len(cfg.steps) == 2
    assert cfg.steps[1].depends_on == ["step1"]


def test_load_valid_fan_out():
    cfg = load_workflow_yaml(VALID_FAN_OUT)
    assert len(cfg.steps) == 3


def test_load_valid_diamond():
    cfg = load_workflow_yaml(VALID_DIAMOND)
    assert len(cfg.steps) == 4
    assert cfg.steps[3].depends_on == ["b", "c"]


def test_default_retries():
    cfg = load_workflow_yaml(VALID_LINEAR)
    assert cfg.steps[0].retries == 3


def test_custom_retries():
    yaml_str = "name: r\nsteps:\n  - id: s1\n    task: parse_text\n    retries: 5"
    cfg = load_workflow_yaml(yaml_str)
    assert cfg.steps[0].retries == 5


def test_cycle_detection():
    with pytest.raises(WorkflowValidationError, match="Cycle detected"):
        load_workflow_yaml(CYCLE_YAML)


def test_unknown_dependency():
    with pytest.raises(WorkflowValidationError, match="depends on unknown step"):
        load_workflow_yaml(UNKNOWN_DEP_YAML)


def test_invalid_yaml():
    with pytest.raises((ValueError, Exception)):
        load_workflow_yaml(": invalid: yaml: :")


def test_missing_name():
    with pytest.raises((ValueError, Exception)):
        load_workflow_yaml("steps:\n  - id: s1\n    task: parse_text\n")


def test_empty_steps():
    cfg = load_workflow_yaml("name: empty\nsteps: []\n")
    assert len(cfg.steps) == 0
