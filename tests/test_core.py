from unittest.mock import MagicMock, patch


def test_health_endpoint():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with (
        patch("workflow_engine.main.db_manager", mock_db),
        patch("workflow_engine.main.redis_manager", mock_redis),
        patch("workflow_engine.main.storage", MagicMock()),
    ):
        from fastapi.testclient import TestClient

        from workflow_engine.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["service"] == "async-workflow-engine"
            assert "dependencies" in response.json()
