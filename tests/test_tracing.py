"""Unit tests for observability/tracing.py."""

import json
import logging
import uuid

from app.observability.tracing import (
    JsonFormatter,
    TraceFilter,
    bind_trace,
    trace_id,
)


def test_bind_trace_sets_contextvar():
    rid = uuid.uuid4()
    bind_trace(rid)
    assert trace_id.get() == str(rid)


def test_trace_filter_injects_trace_id():
    rid = uuid.uuid4()
    bind_trace(rid)

    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    f = TraceFilter()
    f.filter(record)

    assert record.trace_id == str(rid)  # type: ignore[attr-defined]


def test_trace_filter_empty_when_unset():
    # Reset to empty default
    trace_id.set("")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="msg", args=(), exc_info=None,
    )
    TraceFilter().filter(record)
    assert record.trace_id == ""  # type: ignore[attr-defined]


def test_json_formatter_valid_json():
    rid = uuid.uuid4()
    bind_trace(rid)

    record = logging.LogRecord(
        name="test.logger", level=logging.WARNING, pathname="", lineno=0,
        msg="something happened", args=(), exc_info=None,
    )
    record.trace_id = str(rid)

    formatter = JsonFormatter()
    line = formatter.format(record)
    payload = json.loads(line)

    assert payload["level"] == "WARNING"
    assert payload["msg"] == "something happened"
    assert payload["trace_id"] == str(rid)
    assert payload["logger"] == "test.logger"
    assert "time" in payload
