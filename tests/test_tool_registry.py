"""Unit tests for ToolRegistry — no IO, no LLM."""

import asyncio

import pytest

from app.application.agent.tools.base import (
    CapabilityDenied,
    Tool,
    ToolRegistry,
    UnknownTool,
)


async def _echo(inp: dict) -> str:
    return inp.get("text", "ok")


async def _slow(inp: dict) -> str:
    await asyncio.sleep(99)
    return "never"


def _make_tool(name: str = "t", capability: str | None = None) -> Tool:
    return Tool(
        name=name,
        description="desc",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_echo,
        capability=capability,
    )


# ── schemas() ────────────────────────────────────────────────────────────────


def test_schemas_no_capability_always_visible():
    reg = ToolRegistry()
    reg.register(_make_tool("t1"))
    schemas = reg.schemas()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "t1"


def test_schemas_capability_hidden_when_not_allowed():
    reg = ToolRegistry(allowed=set())
    reg.register(_make_tool("t_net", capability="network"))
    assert reg.schemas() == []


def test_schemas_capability_visible_when_allowed():
    reg = ToolRegistry(allowed={"network"})
    reg.register(_make_tool("t_net", capability="network"))
    assert len(reg.schemas()) == 1


def test_schemas_mixed_capabilities():
    reg = ToolRegistry(allowed={"network"})
    reg.register(_make_tool("always"))
    reg.register(_make_tool("net", capability="network"))
    reg.register(_make_tool("fs", capability="fs_read"))
    names = {s["name"] for s in reg.schemas()}
    assert names == {"always", "net"}


# ── dispatch() ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatch_calls_handler():
    reg = ToolRegistry()
    reg.register(_make_tool("t"))
    result = await reg.dispatch("t", {"text": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_dispatch_unknown_raises():
    reg = ToolRegistry()
    with pytest.raises(UnknownTool):
        await reg.dispatch("nope", {})


@pytest.mark.asyncio
async def test_dispatch_denied_capability_raises():
    reg = ToolRegistry(allowed=set())
    reg.register(_make_tool("net", capability="network"))
    with pytest.raises(CapabilityDenied):
        await reg.dispatch("net", {})


@pytest.mark.asyncio
async def test_dispatch_timeout_raises():
    reg = ToolRegistry()
    slow = Tool(
        name="slow",
        description="d",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=_slow,
        timeout=0.05,
    )
    reg.register(slow)
    with pytest.raises(asyncio.TimeoutError):
        await reg.dispatch("slow", {})
