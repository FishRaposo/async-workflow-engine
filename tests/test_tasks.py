import pytest

from workflow_engine.tasks import (
    TASK_REGISTRY,
    _simulate_classification,
    classify_with_llm,
    parse_text,
    send_notification,
)


class TestParseText:
    def test_returns_stats(self):
        result = parse_text(params={"text": "hello world from acme"})
        assert result["status"] == "parsed"
        assert result["word_count"] == 4
        assert result["chunk_count"] >= 1

    def test_default_text(self):
        result = parse_text()
        assert result["word_count"] > 0


class TestClassifyWithLLM:
    def test_mocked_response_short_circuits(self):
        result = classify_with_llm(params={"mocked_response": "business"})
        assert result == {"category": "business", "source": "mock"}

    def test_simulated_classification_offline(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = classify_with_llm(
            params={
                "text": "this is clearly spam spam spam",
                "labels": ["business", "spam"],
            }
        )
        assert result["category"] == "spam"
        assert result["source"] == "sim"

    def test_reads_text_from_context_step(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = classify_with_llm(
            context={"prev": "business business"},
            params={"from_step": "prev", "labels": ["business", "spam"]},
        )
        assert result["category"] == "business"

    def test_deterministic(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        a = classify_with_llm(params={"text": "neutral text", "labels": ["x", "y"]})
        b = classify_with_llm(params={"text": "neutral text", "labels": ["x", "y"]})
        assert a == b


class TestSimulateClassification:
    def test_picks_most_present_label(self):
        assert _simulate_classification("buy buy buy", ["buy", "sell"]) == "buy"

    def test_no_signal_is_deterministic(self):
        labels = ["a", "b", "c"]
        first = _simulate_classification("zzz", labels)
        second = _simulate_classification("zzz", labels)
        assert first == second
        assert first in labels

    def test_no_signal_uses_stable_hash_not_builtin_hash(self):
        # Regression: the no-signal fallback must use a stable hash (sha256), not
        # the process-randomized built-in hash(), so it is reproducible across
        # restarts (PYTHONHASHSEED). Pin the exact label sha256 selects.
        import hashlib

        text = "zzz"
        labels = ["a", "b", "c"]
        expected = labels[
            int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % len(labels)
        ]
        assert _simulate_classification(text, labels) == expected


class TestSendNotification:
    def test_returns_sent(self):
        result = send_notification(params={"channel": "slack", "message": "hi"})
        assert result["status"] == "sent"
        assert result["channel"] == "slack"

    def test_includes_context_keys(self):
        result = send_notification(context={"a": 1, "b": 2})
        assert result["context_keys"] == ["a", "b"]


class TestTaskRegistry:
    def test_contains_all_tasks(self):
        for name in ("parse_text", "classify_with_llm", "send_notification"):
            assert name in TASK_REGISTRY

    def test_values_callable(self):
        for name, fn in TASK_REGISTRY.items():
            assert callable(fn), name

    def test_tasks_accept_context_and_params(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        for name, fn in TASK_REGISTRY.items():
            if name == "always_fail":
                with pytest.raises(RuntimeError):
                    fn(context={}, params={})
            else:
                assert fn(context={"k": "v"}, params={"text": "x"})
