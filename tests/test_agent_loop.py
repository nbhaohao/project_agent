"""AgentLoop — fake LLM client and fake registry, no network calls."""

from dataclasses import dataclass, field

import pytest

from app.application.agent.loop import AgentLoop
from app.application.agent.tools.base import Tool, ToolRegistry


@dataclass
class FakeBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict = field(default_factory=dict)


@dataclass
class FakeResponse:
    content: list
    stop_reason: str


class FakeLLMClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = iter(responses)

    async def complete(self, messages, tools, system=""):
        return next(self._responses)


async def _noop(inp: dict) -> str:
    return "tool-result"


def _make_registry(*names: str) -> ToolRegistry:
    reg = ToolRegistry()
    for name in names:
        reg.register(Tool(
            name=name,
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_noop,
        ))
    return reg


def _loop(responses, max_iterations=50) -> AgentLoop:
    return AgentLoop(
        llm=FakeLLMClient(responses),
        registry=_make_registry("get_current_time"),
        max_iterations=max_iterations,
    )


async def test_ends_on_text_response():
    loop = _loop([FakeResponse([FakeBlock("text", text="Hello!")], "end_turn")])
    assert await loop.run("say hello") == "Hello!"


async def test_dispatches_tool_then_continues():
    loop = _loop([
        FakeResponse(
            [FakeBlock("tool_use", id="t1", name="get_current_time", input={})],
            "tool_use",
        ),
        FakeResponse([FakeBlock("text", text="Done.")], "end_turn"),
    ])
    assert await loop.run("what time is it?") == "Done."


async def test_raises_on_max_iterations():
    always_tool = FakeResponse(
        [FakeBlock("tool_use", id="t1", name="get_current_time", input={})],
        "tool_use",
    )

    class InfiniteClient:
        async def complete(self, **_):
            return always_tool

    loop = AgentLoop(
        llm=InfiniteClient(),
        registry=_make_registry("get_current_time"),
        max_iterations=3,
    )
    with pytest.raises(RuntimeError, match="exceeded"):
        await loop.run("go")


async def test_unknown_tool_returns_error_string_not_raise():
    loop = _loop([
        FakeResponse(
            [FakeBlock("tool_use", id="t1", name="nonexistent_tool", input={})],
            "tool_use",
        ),
        FakeResponse([FakeBlock("text", text="handled.")], "end_turn"),
    ])
    # registry raises UnknownTool — loop wraps it as tool_result string and continues
    assert await loop.run("use unknown tool") == "handled."
