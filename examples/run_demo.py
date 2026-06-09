import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from workflow_engine.executor import WorkflowExecutor
from workflow_engine.parser import load_workflow_yaml
from workflow_engine.tasks import TASK_REGISTRY


def main():
    yaml_def = """
name: lead_intake
steps:
  - id: parse_input
    task: parse_text
  - id: classify
    task: classify_with_llm
    depends_on:
      - parse_input
  - id: notify
    task: send_notification
    depends_on:
      - classify
"""
    print("--- Running Workflow Engine Scaffolding Demo ---")
    config = load_workflow_yaml(yaml_def)
    executor = WorkflowExecutor(config, TASK_REGISTRY)
    results = executor.execute()
    print("Execution results:", results)

if __name__ == "__main__":
    main()
