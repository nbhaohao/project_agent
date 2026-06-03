"""Unit tests for MeteredLLMClient."""

import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

from app.infrastructure.llm import MeteredLLMClient


def _fake_response(input_tokens: int, output_tokens: int, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


async def test_metered_accumulates_usage():
    inner = AsyncMock()
    inner.complete.side_effect = [
        _fake_response(100, 50),
        _fake_response(200, 80),
    ]
    client = MeteredLLMClient(inner)

    await client.complete(messages=[], tools=[])
    await client.complete(messages=[], tools=[])

    assert client.metrics.usage.input_tokens == 300
    assert client.metrics.usage.output_tokens == 130
    assert client.metrics.llm_calls == 2


async def test_metered_passes_through_response():
    inner = AsyncMock()
    resp = _fake_response(10, 5)
    inner.complete.return_value = resp
    client = MeteredLLMClient(inner)

    result = await client.complete(messages=[], tools=[])

    assert result is resp


async def test_metered_handles_missing_usage():
    """If response has no .usage attribute, metrics stay zero (don't crash)."""
    inner = AsyncMock()
    inner.complete.return_value = SimpleNamespace(
        content=[], stop_reason="end_turn", usage=None
    )
    client = MeteredLLMClient(inner)

    await client.complete(messages=[], tools=[])

    assert client.metrics.usage.input_tokens == 0
    assert client.metrics.llm_calls == 0
