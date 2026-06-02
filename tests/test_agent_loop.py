"""AgentLoop — fake LLM client and fake registry, no network calls."""

from dataclasses import dataclass, field

import pytest

from app.application.agent.loop import AgentLoop
from app.application.agent.tools.base import Tool, ToolRegistry
from app.domain.run import RunCancelled


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


async def test_on_message_called_for_each_turn():
    calls: list[tuple[str, object]] = []

    async def capture(role: str, content: object) -> None:
        calls.append((role, content))

    loop = _loop([
        FakeResponse(
            [FakeBlock("tool_use", id="t1", name="get_current_time", input={})],
            "tool_use",
        ),
        FakeResponse([FakeBlock("text", text="Done.")], "end_turn"),
    ])
    await loop.run("go", on_message=capture)

    # user(initial) → assistant(tool_use) → user(tool_result) → assistant(text)
    assert len(calls) == 4
    assert calls[0][0] == "user"       # initial input normalised to list
    assert calls[1][0] == "assistant"  # tool_use block
    assert calls[2][0] == "user"       # tool_result
    assert calls[3][0] == "assistant"  # final text


async def test_should_cancel_raises_run_cancelled():
    loop = _loop([FakeResponse([FakeBlock("text", text="Hello!")], "end_turn")])

    async def always_cancel() -> bool:
        return True

    with pytest.raises(RunCancelled):
        await loop.run("go", should_cancel=always_cancel)


async def test_should_cancel_checked_before_llm_call():
    # Cancels on iteration 2 — LLM is only called once (first iteration completes)
    calls = 0

    async def cancel_on_second() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    loop = _loop([
        FakeResponse(
            [FakeBlock("tool_use", id="t1", name="get_current_time", input={})],
            "tool_use",
        ),
        FakeResponse([FakeBlock("text", text="Done.")], "end_turn"),
    ])
    with pytest.raises(RunCancelled):
        await loop.run("go", should_cancel=cancel_on_second)


async def test_compaction_triggered_when_context_limit_exceeded():
    # context_limit=1 forces compaction every iteration; keep_recent=1 keeps only
    # the most recent message (plus the first), so we can assert exact shape.
    captured: list[list[dict]] = []

    class CapturingLLM:
        _responses = iter([
            FakeResponse([FakeBlock("tool_use", id="t1", name="get_current_time", input={})], "tool_use"),
            FakeResponse([FakeBlock("tool_use", id="t2", name="get_current_time", input={})], "tool_use"),
            FakeResponse([FakeBlock("text", text="Done.")], "end_turn"),
        ])

        async def complete(self, messages, tools, system=""):
            captured.append(list(messages))
            return next(self._responses)

    loop = AgentLoop(
        llm=CapturingLLM(),
        registry=_make_registry("get_current_time"),
        context_limit=1,   # always over the limit
        keep_recent=1,     # keep first + last 1
    )
    result = await loop.run("do a thing")
    assert result == "Done."

    # Call 1: [user_init] — only initial message, no compaction yet
    assert captured[0][0]["role"] == "user"

    # Call 3: compaction has run; messages should be [first_user, most_recent_user]
    # (not the full 5-message history that would exist without compaction)
    assert len(captured[2]) == 2
    assert captured[2][0]["role"] == "user"   # original task preserved


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
