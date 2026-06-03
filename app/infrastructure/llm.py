"""AsyncAnthropic adapter for the LLMClient port."""

from anthropic import AsyncAnthropic

from app.config import settings
from app.domain.usage import RunMetrics, Usage


class AnthropicLLMClient:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url or None,
        )

    async def complete(self, messages: list[dict], tools: list[dict], system: str = ""):
        return await self._client.messages.create(
            model=settings.model_id,
            max_tokens=8096,
            system=system,
            messages=messages,
            tools=tools,
        )


class MeteredLLMClient:
    """Decorator that accumulates token usage from each LLM call into RunMetrics."""

    def __init__(self, inner: AnthropicLLMClient) -> None:
        self._inner = inner
        self.metrics = RunMetrics()

    async def complete(self, messages: list[dict], tools: list[dict], system: str = ""):
        response = await self._inner.complete(messages=messages, tools=tools, system=system)
        if hasattr(response, "usage") and response.usage is not None:
            self.metrics.record_call(
                Usage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
            )
        return response
