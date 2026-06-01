"""Agent execution loop — LLM ↔ tool dispatch cycle.

Extracted from my-agent's agent_loop(); stripped to the minimal M3 skeleton:
no compaction, no memory, no sub-agents (those come in M7/M8/M9).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.agent.tools.base import ToolRegistry
    from app.application.ports import LLMClient

MAX_ITERATIONS = 50


async def _noop(*_: object) -> None:
    pass


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
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations

    async def run(
        self,
        input: str,
        system: str = "",
        on_message: Callable[..., Awaitable[None]] = _noop,
    ) -> str:
        # Normalise initial user input to list-of-blocks for consistent storage
        await on_message("user", [{"type": "text", "text": input}])
        messages: list[dict] = [{"role": "user", "content": input}]

        for _ in range(self._max_iterations):
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
