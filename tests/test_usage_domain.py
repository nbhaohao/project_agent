"""Unit tests for Usage / RunMetrics domain models."""

from app.domain.usage import Usage, RunMetrics, compute_cost


def test_compute_cost_deepseek():
    cost = compute_cost("deepseek-chat", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 1.37) < 1e-6


def test_compute_cost_unknown_model_zero():
    assert compute_cost("unknown-model-xyz", 999, 999) == 0.0


def test_usage_iadd():
    u = Usage(100, 50)
    u += Usage(200, 80)
    assert u.input_tokens == 300
    assert u.output_tokens == 130
    assert u.total_tokens == 430


def test_run_metrics_record_call():
    m = RunMetrics()
    m.record_call(Usage(500, 200))
    m.record_call(Usage(300, 100))
    assert m.usage.input_tokens == 800
    assert m.usage.output_tokens == 300
    assert m.llm_calls == 2


def test_run_metrics_cost():
    m = RunMetrics()
    m.record_call(Usage(1_000_000, 0))
    cost = m.cost("deepseek-chat")
    assert abs(cost - 0.27) < 1e-6
