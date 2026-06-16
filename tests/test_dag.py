from workflow_engine.dag import build_dag
from workflow_engine.parser import load_workflow_yaml

BRANCHING = """\
name: b
steps:
  - id: a
    task: parse_text
  - id: classify
    task: classify_with_llm
    depends_on: [a]
  - id: notify
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: business
"""


def test_build_dag_nodes_and_edges():
    cfg = load_workflow_yaml(BRANCHING)
    dag = build_dag(cfg)
    node_ids = {n["id"] for n in dag["nodes"]}
    assert node_ids == {"a", "classify", "notify"}
    dep_edges = [e for e in dag["edges"] if e["type"] == "dependency"]
    assert {"from": "a", "to": "classify", "type": "dependency"} in dep_edges


def test_build_dag_marks_conditional():
    cfg = load_workflow_yaml(BRANCHING)
    dag = build_dag(cfg)
    notify = next(n for n in dag["nodes"] if n["id"] == "notify")
    assert notify["conditional"] is True
    cond_edges = [e for e in dag["edges"] if e["type"] == "conditional"]
    assert {"from": "classify", "to": "notify", "type": "conditional"} in cond_edges


def test_build_dag_applies_statuses():
    cfg = load_workflow_yaml(BRANCHING)
    dag = build_dag(cfg, {"a": "COMPLETED", "classify": "RUNNING"})
    statuses = {n["id"]: n["status"] for n in dag["nodes"]}
    assert statuses["a"] == "COMPLETED"
    assert statuses["classify"] == "RUNNING"
    assert statuses["notify"] == "PENDING"  # default when not provided
