"""Token usage and cost tracking domain models.

Pricing table: input/output cost per million tokens by model prefix.
Cost is computed at domain boundary — infra passes raw token counts, domain owns the math.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# USD per million tokens, keyed by model prefix (longest match wins).
# Add entries as more models are used.
_PRICING: list[tuple[str, float, float]] = [
    # prefix               input  output
    ("deepseek-chat",      0.27,  1.10),
    ("deepseek-reasoner",  0.55,  2.19),
    ("claude-opus",       15.00, 75.00),
    ("claude-sonnet",      3.00, 15.00),
    ("claude-haiku",       0.25,  1.25),
]
_FALLBACK_PRICING = (0.0, 0.0)


def _unit_cost(model_id: str) -> tuple[float, float]:
    for prefix, inp, out in _PRICING:
        if model_id.startswith(prefix):
            return inp, out
    return _FALLBACK_PRICING


def compute_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    inp_price, out_price = _unit_cost(model_id)
    return (input_tokens * inp_price + output_tokens * out_price) / 1_000_000


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __iadd__(self, other: Usage) -> Usage:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        return self

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class RunMetrics:
    usage: Usage = field(default_factory=Usage)
    llm_calls: int = 0

    def record_call(self, u: Usage) -> None:
        self.usage += u
        self.llm_calls += 1

    def cost(self, model_id: str) -> float:
        return compute_cost(model_id, self.usage.input_tokens, self.usage.output_tokens)
