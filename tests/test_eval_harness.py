"""Unit tests for eval harness — mock httpx, no live API needed."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eval.harness import CaseResult, _run_case


def _sse(*events: dict) -> list[str]:
    """Build a list of SSE data lines from event dicts."""
    return [f"data: {json.dumps(e)}" for e in events]


def _mock_client(submit_status: int, submit_body: dict, sse_lines: list[str]):
    """Build a mock httpx.AsyncClient for one case."""
    client = MagicMock()

    # POST /runs
    post_resp = MagicMock()
    post_resp.raise_for_status = MagicMock()
    post_resp.json.return_value = submit_body
    post_resp.status_code = submit_status
    client.post = AsyncMock(return_value=post_resp)

    # GET /runs/{id}/events — async context manager that yields lines
    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    async def _aiter_lines():
        for line in sse_lines:
            yield line

    stream_ctx.aiter_lines = _aiter_lines
    client.stream = MagicMock(return_value=stream_ctx)
    return client


async def test_harness_pass_tool_called():
    sse = _sse(
        {"type": "tool_call", "tool": "get_current_time", "input": {}},
        {"type": "tool_result", "output": "2026-06-03T10:00:00Z"},
        {"type": "text", "text": "It is 10:00 UTC."},
        {"type": "done", "result": "It is 10:00 UTC.",
         "input_tokens": 100, "output_tokens": 30, "cost_usd": 0.000123, "llm_calls": 1},
    )
    client = _mock_client(201, {"id": "run-abc"}, sse)
    case = {"id": "time-001", "description": "time test", "input": "What time is it?",
            "assert": {"tool_called": "get_current_time"}}

    result = await _run_case(client, case)

    assert result.passed is True
    assert result.run_status == "succeeded"
    assert result.input_tokens == 100
    assert result.llm_calls == 1
    assert "get_current_time" in result.tool_calls


async def test_harness_pass_contains():
    sse = _sse(
        {"type": "done", "result": "The JSON contains a slideshow field.",
         "input_tokens": 200, "output_tokens": 50, "cost_usd": 0.0, "llm_calls": 2},
    )
    client = _mock_client(201, {"id": "run-xyz"}, sse)
    case = {"id": "fetch-001", "description": "fetch test", "input": "fetch url",
            "assert": {"contains": "slideshow"}}

    result = await _run_case(client, case)

    assert result.passed is True


async def test_harness_fail_contains():
    sse = _sse(
        {"type": "done", "result": "I fetched the page, it has some data.",
         "input_tokens": 80, "output_tokens": 20, "cost_usd": 0.0, "llm_calls": 1},
    )
    client = _mock_client(201, {"id": "run-fail"}, sse)
    case = {"id": "fetch-002", "description": "fail test", "input": "fetch",
            "assert": {"contains": "slideshow"}}

    result = await _run_case(client, case)

    assert result.passed is False
    assert "slideshow" in result.fail_reason


async def test_harness_fail_tool_not_called():
    sse = _sse(
        {"type": "done", "result": "I guessed the time without using a tool.",
         "input_tokens": 50, "output_tokens": 10, "cost_usd": 0.0, "llm_calls": 1},
    )
    client = _mock_client(201, {"id": "run-notool"}, sse)
    case = {"id": "time-002", "description": "no tool", "input": "time?",
            "assert": {"tool_called": "get_current_time"}}

    result = await _run_case(client, case)

    assert result.passed is False
    assert "get_current_time" in result.fail_reason


async def test_harness_run_failed_status():
    sse = _sse({"type": "error", "error": "agent crashed"})
    client = _mock_client(201, {"id": "run-err"}, sse)
    case = {"id": "err-001", "description": "error case", "input": "boom",
            "assert": {"tool_called": "anything"}}

    result = await _run_case(client, case)

    assert result.passed is False
    assert result.run_status == "error"
