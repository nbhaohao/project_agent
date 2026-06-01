"""SSE event schema and derivation from persisted RunMessages.

Five event types (all plain dicts, JSON-serialisable):
  {"type": "text",        "text": "..."}
  {"type": "tool_call",   "tool": "...", "input": {}}
  {"type": "tool_result", "output": "..."}
  {"type": "done",        "result": "..."}   # emitted by worker on success
  {"type": "error",       "error":  "..."}   # emitted by worker on failure
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.message import RunMessage


def derive_events(message: RunMessage) -> list[dict]:
    """Convert one persisted RunMessage into zero-or-more SSE event dicts."""
    events: list[dict] = []
    for block in message.content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text" and message.role == "assistant":
            text = block.get("text", "")
            if text:
                events.append({"type": "text", "text": text})
        elif btype == "tool_use":
            events.append({
                "type": "tool_call",
                "tool": block.get("name", ""),
                "input": block.get("input", {}),
            })
        elif btype == "tool_result":
            events.append({
                "type": "tool_result",
                "output": block.get("content", ""),
            })
    return events
