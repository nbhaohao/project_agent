"""Tool abstraction — Tool dataclass + ToolRegistry with capability filtering."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


class UnknownTool(Exception):
    pass


class CapabilityDenied(Exception):
    pass


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[str]]
    timeout: float = 10.0
    # None = always available; non-None = requires the capability to be in allowed set
    capability: str | None = None


class ToolRegistry:
    def __init__(self, allowed: set[str] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._allowed: set[str] = allowed or set()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def _visible(self, tool: Tool) -> bool:
        return tool.capability is None or tool.capability in self._allowed

    def schemas(self) -> list[dict]:
        """Return Anthropic-format tool schemas for all visible tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
            if self._visible(t)
        ]

    async def dispatch(self, name: str, tool_input: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownTool(f"unknown tool: {name!r}")
        if not self._visible(tool):
            raise CapabilityDenied(
                f"tool {name!r} requires capability {tool.capability!r}"
            )
        return await asyncio.wait_for(tool.handler(tool_input), tool.timeout)
