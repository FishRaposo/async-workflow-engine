from unittest.mock import MagicMock, patch

VALID_YAML = """\
name: test_flow
steps:
  - id: step1
    task: parse_text
"""


def _make_client():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_storage = MagicMock()

    with (
        patch("workflow_engine.main.db_manager", mock_db),
        patch("workflow_engine.main.redis_manager", mock_redis),
        patch("workflow_engine.main.storage", mock_storage),
    ):
        from fastapi.testclient import TestClient

        from workflow_engine.main import app

        with TestClient(app) as client:
            yield client, mock_storage


def test_validate_valid_workflow():
    gen = _make_client()
    client, _ = next(gen)
    try:
        resp = client.post("/workflows/validate", json={"yaml_definition": VALID_YAML})
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["workflow"] == "test_flow"
    finally:
        gen.close()


def test_validate_cycle():
    cycle_yaml = """\
name: cycle
steps:
  - id: a
    task: parse_text
    depends_on:
      - b
  - id: b
    task: parse_text
    depends_on:
      - a
"""
    gen = _make_client()
    client, _ = next(gen)
    try:
        resp = client.post("/workflows/validate", json={"yaml_definition": cycle_yaml})
        assert resp.status_code == 422
    finally:
        gen.close()


def test_run_workflow():
    gen = _make_client()
    client, mock_storage = next(gen)
    try:
        resp = client.post("/workflows/run", json={"yaml_definition": VALID_YAML})
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow"] == "test_flow"
        assert data["step_statuses"]["step1"] == "COMPLETED"
        assert "run_id" in data
        assert mock_storage.save_run.called
    finally:
        gen.close()


def test_list_tasks():
    gen = _make_client()
    client, _ = next(gen)
    try:
        resp = client.get("/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        task_names = [t["name"] for t in data["tasks"]]
        assert "parse_text" in task_names
        assert "classify_with_llm" in task_names
    finally:
        gen.close()
