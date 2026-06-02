"""compaction — estimate_tokens + compact_messages pure-function tests."""

from app.application.agent.compaction import compact_messages, estimate_tokens


def _msg(role: str, text: str) -> dict:
    return {"role": role, "content": text}


def test_estimate_tokens_proportional_to_content():
    msgs = [_msg("user", "hello")]
    assert estimate_tokens(msgs) > 0
    assert estimate_tokens([_msg("user", "x" * 400)]) == pytest.approx(100, abs=10)


def test_compact_noop_when_short():
    msgs = [_msg("user", f"msg {i}") for i in range(5)]
    assert compact_messages(msgs, keep_recent=10) is msgs


def test_compact_keeps_first_and_last():
    msgs = [_msg("user", f"msg {i}") for i in range(20)]
    result = compact_messages(msgs, keep_recent=5)

    assert result[0] == msgs[0]           # original task preserved
    assert result[1:] == msgs[-5:]        # last 5 retained
    assert len(result) == 6


def test_compact_drops_middle():
    msgs = [_msg("user", f"msg {i}") for i in range(15)]
    result = compact_messages(msgs, keep_recent=4)

    # msgs[1..10] should be gone
    middle = set(m["content"] for m in msgs[1:-4])
    result_content = set(m["content"] for m in result)
    assert middle.isdisjoint(result_content)


def test_compact_exactly_at_boundary_is_noop():
    # keep_recent=4 → min_len=5; list of 5 should not be compacted
    msgs = [_msg("user", f"msg {i}") for i in range(5)]
    assert compact_messages(msgs, keep_recent=4) is msgs


import pytest
