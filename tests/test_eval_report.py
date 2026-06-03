"""Unit tests for eval/__main__.py report formatting."""

import io
import sys

from eval.__main__ import print_report
from eval.harness import CaseResult


def _capture(results):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        print_report(results)
    finally:
        sys.stdout = old
    return buf.getvalue()


def _make(id_, passed, *, lat=1.0, in_tok=100, out_tok=30, cost=0.000027, calls=1,
          fail_reason=None):
    return CaseResult(
        id=id_, description="desc", passed=passed,
        fail_reason=fail_reason, run_status="succeeded" if passed else "failed",
        latency_s=lat, input_tokens=in_tok, output_tokens=out_tok,
        cost_usd=cost, llm_calls=calls,
    )


def test_report_all_pass_summary():
    results = [_make("time-001", True), _make("fetch-001", True)]
    out = _capture(results)
    assert "2/2 passed" in out
    assert "↑" in out
    assert "$" in out


def test_report_fail_shows_reason():
    results = [_make("fetch-001", False, fail_reason="result does not contain 'slideshow'")]
    out = _capture(results)
    assert "slideshow" in out
    assert "❌" in out


def test_report_partial_pass_summary():
    results = [_make("a", True), _make("b", False, fail_reason="oops"), _make("c", True)]
    out = _capture(results)
    assert "2/3 passed" in out


def test_report_cost_aggregated():
    results = [
        _make("a", True, cost=0.000100),
        _make("b", True, cost=0.000200),
    ]
    out = _capture(results)
    # total cost = 0.000300
    assert "0.000300" in out


def test_report_none_metrics_renders_dash():
    r = CaseResult(id="x", description="d", passed=False,
                   run_status="harness_error", fail_reason="submit failed: timeout",
                   latency_s=0.5)
    out = _capture([r])
    assert "—" in out
