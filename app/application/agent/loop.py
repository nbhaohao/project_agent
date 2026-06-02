"""Agent execution loop — LLM ↔ tool dispatch cycle."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.application.agent.compaction import compact_messages, estimate_tokens
from app.domain.run import RunCancelled

if TYPE_CHECKING:
    from app.application.agent.tools.base import ToolRegistry
    from app.application.ports import LLMClient

MAX_ITERATIONS = 50
DEFAULT_CONTEXT_LIMIT = 80_000  # tokens; compact before hitting model window


async def _noop(*_: object) -> None:
    pass


async def _no_cancel() -> bool:
    return False


def _extract_text(content: list) -> str:
    for block in content:
        if getattr(block, "type", None) == "text":
            return getattr(block, "text", "")
    return ""


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        max_iterations: int = MAX_ITERATIONS,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
        keep_recent: int = 10,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        self._context_limit = context_limit
        self._keep_recent = keep_recent

    async def run(
        self,
        input: str,
        system: str = "",
        on_message: Callable[..., Awaitable[None]] = _noop,
        should_cancel: Callable[[], Awaitable[bool]] = _no_cancel,
    ) -> str:
        # Normalise initial user input to list-of-blocks for consistent storage
        await on_message("user", [{"type": "text", "text": input}])
        messages: list[dict] = [{"role": "user", "content": input}]

        for _ in range(self._max_iterations):
            if await should_cancel():
                raise RunCancelled("run was cancelled")
            if estimate_tokens(messages) > self._context_limit:
                messages = compact_messages(messages, keep_recent=self._keep_recent)
            response = await self._llm.complete(
                messages=messages,
                tools=self._registry.schemas(),
                system=system,
            )
            await on_message("assistant", response.content)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return _extract_text(response.content)

            results = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    try:
                        output = await self._registry.dispatch(block.name, block.input)
                    except Exception as exc:
                        output = f"tool error: {exc}"
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            await on_message("user", results)
            messages.append({"role": "user", "content": results})

        raise RuntimeError(
            f"agent exceeded {self._max_iterations} iterations without finishing"
        )
