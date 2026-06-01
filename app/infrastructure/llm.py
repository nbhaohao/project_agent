"""AsyncAnthropic adapter for the LLMClient port."""

from anthropic import AsyncAnthropic

from app.config import settings


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
