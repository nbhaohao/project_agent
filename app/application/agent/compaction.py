"""Context compaction — keep messages within token budget.

Strategy: keep-first-keep-last
  - Always preserve messages[0] (the original user task)
  - Drop middle messages when estimated token count exceeds the limit
  - Retain the most recent `keep_recent` messages for current context
"""

import json

_CHARS_PER_TOKEN = 4  # rough but provider-agnostic estimate


def estimate_tokens(messages: list[dict]) -> int:
    return sum(len(json.dumps(m)) for m in messages) // _CHARS_PER_TOKEN


def compact_messages(messages: list[dict], *, keep_recent: int = 10) -> list[dict]:
    """Return a compacted copy; no-op when messages are short enough."""
    min_len = keep_recent + 1  # first message + keep_recent tail
    if len(messages) <= min_len:
        return messages
    return [messages[0]] + messages[-keep_recent:]
