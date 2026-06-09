import pytest
from workflow_engine.tasks import (
    TASK_REGISTRY,
    classify_with_llm,
    parse_text,
    send_notification,
)


class TestTaskFunctions:
    def test_parse_text_returns_string(self):
        result = parse_text()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_parse_text_with_context(self):
        result = parse_text(context={"input": "test"})
        assert result == "metadata_parsed"

    def test_classify_with_llm_returns_string(self):
        result = classify_with_llm()
        assert "category" in result.lower() or isinstance(result, str)

    def test_send_notification_returns_string(self):
        result = send_notification()
        assert "notification" in result.lower() or "sent" in result.lower()


class TestTaskRegistry:
    def test_registry_contains_all_tasks(self):
        assert "parse_text" in TASK_REGISTRY
        assert "classify_with_llm" in TASK_REGISTRY
        assert "send_notification" in TASK_REGISTRY

    def test_registry_values_are_callable(self):
        for name, fn in TASK_REGISTRY.items():
            assert callable(fn), f"TASK_REGISTRY['{name}'] is not callable"

    def test_registry_tasks_produce_results(self):
        for name, fn in TASK_REGISTRY.items():
            result = fn()
            assert result, f"Task '{name}' returned empty result"

    def test_all_registry_tasks_accept_context(self):
        for name, fn in TASK_REGISTRY.items():
            result = fn(context={"test": "value"})
            assert result, f"Task '{name}' failed with context arg"
