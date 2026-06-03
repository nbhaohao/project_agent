"""Lightweight tracing: trace_id contextvar + JSON structured logging.

trace_id is set once per run at worker entry (_process_one) and then
inherited automatically by all coroutines awaited in the same task,
including sub-agents (they're awaited inline, not spawned as new tasks).
asyncio.create_task() also copies the current context, so the watchdog
task inherits trace_id without any extra wiring.
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid

trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def bind_trace(run_id: uuid.UUID) -> None:
    """Bind trace_id to the current async context for this run."""
    trace_id.set(str(run_id))


class TraceFilter(logging.Filter):
    """Injects trace_id from the current context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id.get()  # type: ignore[attr-defined]
        return True


class JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", ""),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Replace root logger handlers with a single JSON+trace handler."""
    handler = logging.StreamHandler()
    handler.addFilter(TraceFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
