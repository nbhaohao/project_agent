"""Unit tests for derive_events — pure logic, no IO."""

import uuid
from datetime import UTC, datetime

from app.application.agent.events import derive_events
from app.domain.message import RunMessage


def _msg(role: str, content: list) -> RunMessage:
    return RunMessage(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        seq=0,
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )


def test_assistant_text_block_emits_text_event():
    msg = _msg("assistant", [{"type": "text", "text": "Hello!"}])
    assert derive_events(msg) == [{"type": "text", "text": "Hello!"}]


def test_empty_text_block_skipped():
    msg = _msg("assistant", [{"type": "text", "text": ""}])
    assert derive_events(msg) == []


def test_tool_use_block_emits_tool_call_event():
    msg = _msg("assistant", [{"type": "tool_use", "name": "get_current_time", "input": {}}])
    assert derive_events(msg) == [{"type": "tool_call", "tool": "get_current_time", "input": {}}]


def test_tool_result_block_emits_tool_result_event():
    msg = _msg("user", [{"type": "tool_result", "tool_use_id": "t1", "content": "2026-06-02T00:00:00"}])
    assert derive_events(msg) == [{"type": "tool_result", "output": "2026-06-02T00:00:00"}]


def test_user_text_block_emits_no_event():
    # initial user input — frontend already shows it, no need to replay
    msg = _msg("user", [{"type": "text", "text": "What time is it?"}])
    assert derive_events(msg) == []


def test_multiple_blocks_emit_multiple_events():
    msg = _msg("assistant", [
        {"type": "tool_use", "name": "http_fetch", "input": {"url": "https://example.com"}},
        {"type": "text", "text": "Here is the result."},
    ])
    events = derive_events(msg)
    assert len(events) == 2
    assert events[0]["type"] == "tool_call"
    assert events[1]["type"] == "text"


def test_non_dict_block_skipped():
    msg = _msg("assistant", ["unexpected_string", {"type": "text", "text": "ok"}])
    assert derive_events(msg) == [{"type": "text", "text": "ok"}]
