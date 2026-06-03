"""Eval harness — runs each dataset case against the live API and collects results.

Usage (called by eval/__main__.py):
    results = await run_eval(base_url="http://localhost:8000")

Each case submits a run, streams SSE events to collect tool_calls + final
result, then checks deterministic assertions (contains / tool_called).
Cases run sequentially to keep load predictable; sub-agent cases need ~120s.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

DATASET_PATH = Path(__file__).parent / "dataset.json"
DEFAULT_BASE_URL = "http://localhost:8000"
PER_CASE_TIMEOUT = 200.0  # sub-agent cases can take ~120s


@dataclass
class CaseResult:
    id: str
    description: str
    passed: bool
    fail_reason: str | None = None
    # "succeeded" | "failed" | "cancelled" | "harness_error"
    run_status: str = "unknown"
    latency_s: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    llm_calls: int | None = None
    tool_calls: list[str] = field(default_factory=list)


async def _run_case(client: httpx.AsyncClient, case: dict) -> CaseResult:
    case_id = case["id"]
    description = case.get("description", "")
    assertion = case["assert"]
    t0 = time.monotonic()

    # 1. Submit run
    try:
        resp = await client.post("/runs", json={"input": case["input"]})
        resp.raise_for_status()
        run_id = resp.json()["id"]
    except Exception as exc:
        return CaseResult(
            id=case_id, description=description, passed=False,
            fail_reason=f"submit failed: {exc}", run_status="harness_error",
            latency_s=time.monotonic() - t0,
        )

    # 2. Stream SSE events to collect tool_calls + terminal event
    tool_calls: list[str] = []
    result_text: str | None = None
    run_status = "unknown"
    input_tokens = output_tokens = cost_usd = llm_calls = None

    try:
        async with client.stream(
            "GET", f"/runs/{run_id}/events", timeout=PER_CASE_TIMEOUT
        ) as stream:
            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                etype = evt.get("type")
                if etype == "tool_call":
                    tool_calls.append(evt.get("tool", ""))
                elif etype == "done":
                    result_text = evt.get("result", "")
                    input_tokens = evt.get("input_tokens")
                    output_tokens = evt.get("output_tokens")
                    cost_usd = evt.get("cost_usd")
                    llm_calls = evt.get("llm_calls")
                    run_status = "succeeded"
                    break
                elif etype in ("error", "cancelled"):
                    run_status = etype
                    break
    except Exception as exc:
        return CaseResult(
            id=case_id, description=description, passed=False,
            fail_reason=f"stream error: {exc}", run_status="harness_error",
            latency_s=time.monotonic() - t0, tool_calls=tool_calls,
        )

    latency_s = time.monotonic() - t0
    base = CaseResult(
        id=case_id, description=description, passed=False,
        run_status=run_status, latency_s=latency_s,
        input_tokens=input_tokens, output_tokens=output_tokens,
        cost_usd=cost_usd, llm_calls=llm_calls, tool_calls=tool_calls,
    )

    # 3. Gate: run must have succeeded
    if run_status != "succeeded":
        base.fail_reason = f"run did not succeed (status={run_status})"
        return base

    # 4. Check assertions
    if "contains" in assertion:
        needle = assertion["contains"].lower()
        if needle not in (result_text or "").lower():
            base.fail_reason = (
                f"result does not contain '{assertion['contains']}'"
            )
            return base

    if "tool_called" in assertion:
        expected = assertion["tool_called"]
        if expected not in tool_calls:
            base.fail_reason = (
                f"tool '{expected}' was not called (called: {tool_calls})"
            )
            return base

    base.passed = True
    return base


async def run_eval(base_url: str = DEFAULT_BASE_URL) -> list[CaseResult]:
    """Run all dataset cases sequentially; return one CaseResult per case."""
    cases: list[dict] = json.loads(DATASET_PATH.read_text())
    results: list[CaseResult] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=PER_CASE_TIMEOUT) as client:
        for case in cases:
            result = await _run_case(client, case)
            results.append(result)
    return results
