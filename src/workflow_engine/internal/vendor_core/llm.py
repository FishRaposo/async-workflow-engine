import asyncio
import time
from typing import Any, Optional

from pydantic import BaseModel, Field

# Static cost table per 1M tokens (Input, Output) in USD
MODEL_COSTS = {
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-mini": (0.150, 0.600),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
}


def estimate_llm_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Helper to calculate LLM completion USD cost.

    Delegates to the local pricing registry, the single source of truth for
    per-model token pricing. ``MODEL_COSTS`` above is retained for backward
    compatibility; new code should prefer that registry.
    """
    from workflow_engine.internal.vendor_core.pricing import calculate_cost

    return calculate_cost(model, prompt_tokens, completion_tokens)


class LLMResponse(BaseModel):
    """Standardized response structure for LLM calls across all repositories."""

    text: str = Field(description="The generated completion text.")
    model: str = Field(description="The model identifier used for generation.")
    prompt_tokens: int = Field(default=0, description="Number of tokens in prompt.")
    completion_tokens: int = Field(
        default=0, description="Number of tokens in completion."
    )
    total_tokens: int = Field(default=0, description="Total token count.")
    latency_ms: float = Field(default=0.0, description="Time taken in milliseconds.")
    estimated_cost: float = Field(
        default=0.0, description="Estimated USD cost of the transaction."
    )


def _unwrap_secret(value: Any) -> Optional[str]:
    """Extract plaintext from SecretStr, or return the value as-is."""
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return value


class LLMClientFactory:
    """Factory to interact with OpenAI and Anthropic APIs dynamically."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
    ):
        self.openai_api_key = _unwrap_secret(openai_api_key)
        self.anthropic_api_key = _unwrap_secret(anthropic_api_key)

    def get_openai_client(self) -> Any:
        """Dynamically imports and returns OpenAI client."""
        try:
            import openai  # type: ignore
        except ImportError:
            raise ImportError(
                "openai module is not installed. "
                "Install it via 'pip install openai' in your service."
            ) from None
        return openai.OpenAI(api_key=self.openai_api_key)

    def get_anthropic_client(self) -> Any:
        """Dynamically imports and returns Anthropic client."""
        try:
            import anthropic  # type: ignore
        except ImportError:
            raise ImportError(
                "anthropic module is not installed. "
                "Install it via 'pip install anthropic' in your service."
            ) from None
        return anthropic.Anthropic(api_key=self.anthropic_api_key)

    async def generate_openai(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Performs async completion call to OpenAI API."""
        try:
            import openai  # type: ignore
        except ImportError:
            raise ImportError("openai module not installed.") from None

        client = openai.AsyncOpenAI(api_key=self.openai_api_key)

        start_time = time.perf_counter()
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency = (time.perf_counter() - start_time) * 1000

        text = response.choices[0].message.content or ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0

        cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)

        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
            estimated_cost=cost,
        )

    async def generate_anthropic(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Performs async completion call to Anthropic API."""
        try:
            import anthropic  # type: ignore
        except ImportError:
            raise ImportError("anthropic module not installed.") from None

        client = anthropic.AsyncAnthropic(api_key=self.anthropic_api_key)

        start_time = time.perf_counter()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        latency = (time.perf_counter() - start_time) * 1000

        text = response.content[0].text if response.content else ""
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        total_tokens = prompt_tokens + completion_tokens

        cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)

        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
            estimated_cost=cost,
        )

    async def generate_mock(self, model: str, prompt: str) -> LLMResponse:
        """Generates a fast mock response for local testing and unit tests."""
        start_time = time.perf_counter()
        await asyncio.sleep(0.05)
        latency = (time.perf_counter() - start_time) * 1000

        prompt_tokens = len(prompt.split())
        text = f"Mock response for prompt: {prompt[:30]}..."
        completion_tokens = len(text.split())
        total_tokens = prompt_tokens + completion_tokens
        cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)

        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency,
            estimated_cost=cost,
        )
