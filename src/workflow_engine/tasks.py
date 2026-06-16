"""Real task implementations and the task registry.

Tasks are plain callables registered by name in :data:`TASK_REGISTRY`. The
executor invokes them as ``task_fn(context=..., params=...)`` where ``context``
holds the results of prior steps (keyed by step id) and ``params`` holds the
step's declared parameters from the YAML.

The tasks are offline-first:

* ``parse_text`` uses ``shared_core.docparse.chunk_text`` to produce real text
  statistics — no network, no API key.
* ``classify_with_llm`` mirrors the llm-cost-latency-monitor SDK pattern: a
  ``mocked_response`` short-circuit, else a real call through
  ``shared_core.llm.LLMClientFactory`` when an API key is configured, with a
  graceful fallback to a deterministic simulated classification.
* ``send_notification`` is a side-effect-free simulated dispatcher.
"""

import hashlib
import os
from typing import Any, Dict, Optional

from loguru import logger
from shared_core.docparse import chunk_text


def parse_text(
    context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse and chunk an input text, returning real statistics.

    Reads ``params['text']`` (or falls back to a sample), chunks it with
    shared_core's deterministic chunker, and returns word/chunk counts. This is
    fully offline.
    """
    params = params or {}
    text = params.get("text") or (
        "Lead inbound: ACME Corp requests a quote for 500 widgets. "
        "Priority customer, follow up within 24h."
    )
    chunk_size = int(params.get("chunk_size", 256))
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=0)
    word_count = len(text.split())
    logger.info(f"parse_text: {word_count} words -> {len(chunks)} chunk(s)")
    return {
        "status": "parsed",
        "word_count": word_count,
        "chunk_count": len(chunks),
        "preview": text[:80],
    }


def _simulate_classification(text: str, labels: list[str]) -> str:
    """Deterministic offline classifier: pick the label most present in text."""
    lowered = text.lower()
    scored = sorted(
        labels,
        key=lambda label: (lowered.count(label.lower()), label),
        reverse=True,
    )
    best = scored[0] if scored else "uncategorized"
    # If no signal at all, hash to a stable label so the result is deterministic.
    # Use a stable hash (sha256) rather than the process-randomized built-in
    # hash() so the choice is reproducible across restarts (PYTHONHASHSEED).
    if best and lowered.count(best.lower()) == 0:
        if labels:
            idx = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % len(
                labels
            )
            best = labels[idx]
        else:
            best = "uncategorized"
    return best


def classify_with_llm(
    context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify text into one of ``params['labels']``.

    Resolution order (mirrors the llm-cost-latency-monitor SDK pattern):

    1. ``params['mocked_response']`` -> returned verbatim (deterministic tests).
    2. A real LLM call via ``shared_core.llm.LLMClientFactory`` when an API key
       is present. ImportError or missing key falls through to (3).
    3. A deterministic offline simulation over ``params['labels']``.
    """
    params = params or {}
    context = context or {}
    labels = list(params.get("labels", ["business", "support", "spam"]))
    text = params.get("text") or str(context.get(params.get("from_step", ""), ""))
    if not text:
        text = "general inquiry"

    mocked = params.get("mocked_response")
    if mocked is not None:
        logger.info("classify_with_llm: using mocked_response")
        return {"category": str(mocked), "source": "mock"}

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import asyncio

            from shared_core.llm import LLMClientFactory

            model = params.get("model", "gpt-4o-mini")
            prompt = (
                f"Classify the following text into exactly one of {labels}. "
                f"Reply with only the label.\n\nText: {text}"
            )
            factory = LLMClientFactory(
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
            if "claude" in model.lower():
                resp = asyncio.run(factory.generate_anthropic(model, prompt))
            else:
                resp = asyncio.run(factory.generate_openai(model, prompt))
            category = resp.text.strip().splitlines()[0].lower()
            return {"category": category, "source": "llm", "model": model}
        except ImportError:
            logger.warning("classify_with_llm: LLM SDK missing — simulating")
        except Exception as exc:  # pragma: no cover - network/credential errors
            logger.warning(f"classify_with_llm: LLM call failed ({exc}) — simulating")

    category = _simulate_classification(text, labels)
    logger.info(f"classify_with_llm: simulated category '{category}'")
    return {"category": category, "source": "sim"}


def send_notification(
    context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Simulate sending a notification (no external I/O).

    Honors ``params['channel']`` and ``params['message']``; if a prior step's
    classification is in context it is embedded into the message.
    """
    params = params or {}
    context = context or {}
    channel = params.get("channel", "email")
    message = params.get("message", "Workflow step completed.")
    logger.info(f"send_notification: dispatching via {channel}: {message}")
    return {
        "status": "sent",
        "channel": channel,
        "message": message,
        "context_keys": sorted(context.keys()),
    }


def always_fail(
    context: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A task that always raises — used to exercise retries and the DLQ."""
    message = (params or {}).get("message", "intentional failure")
    raise RuntimeError(message)


TASK_REGISTRY: Dict[str, Any] = {
    "parse_text": parse_text,
    "classify_with_llm": classify_with_llm,
    "send_notification": send_notification,
    "always_fail": always_fail,
}
