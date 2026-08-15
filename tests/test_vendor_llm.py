"""Optional-provider response guards for the vendored LLM adapter."""

from types import SimpleNamespace

from workflow_engine.internal.vendor_core.llm import _first_textual_content


def test_first_textual_content_skips_non_text_anthropic_blocks() -> None:
    """Tool-use blocks before a text block do not crash Anthropic responses."""
    blocks = [
        SimpleNamespace(type="tool_use", name="lookup"),
        SimpleNamespace(type="text", text="workflow complete"),
    ]

    assert _first_textual_content(blocks) == "workflow complete"
