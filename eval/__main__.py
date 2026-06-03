"""Eval CLI — run the eval suite against the live API and print a report.

Usage:
    uv run python -m eval [--base-url http://localhost:8000]

Exit code 0 if all cases pass, 1 if any fail.
Requires: docker compose up -d + uvicorn + worker all running.
"""

import argparse
import asyncio
import sys

from eval.harness import CaseResult, run_eval


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_tokens(r: CaseResult) -> str:
    if r.input_tokens is None:
        return "—"
    return f"{r.input_tokens}↑ {r.output_tokens}↓"


def _fmt_cost(r: CaseResult) -> str:
    if r.cost_usd is None:
        return "—"
    return f"${r.cost_usd:.6f}"


def _fmt_calls(r: CaseResult) -> str:
    return str(r.llm_calls) if r.llm_calls is not None else "—"


def _fmt_lat(r: CaseResult) -> str:
    return f"{r.latency_s:.1f}s"


# ── Report printer ────────────────────────────────────────────────────────────

def print_report(results: list[CaseResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    id_w = max((len(r.id) for r in results), default=8)

    print()
    print(f"=== Eval Report — project_agent  ({total} cases) ===")
    print()
    print(
        f"  {'ID':<{id_w}}  {'':4}  {'LAT':>7}  {'TOKENS':>18}  {'CALLS':>5}  {'COST':>12}"
    )
    print(
        f"  {'─'*id_w}  {'─'*4}  {'─'*7}  {'─'*18}  {'─'*5}  {'─'*12}"
    )

    for r in results:
        icon = "✅" if r.passed else "❌"
        print(
            f"  {r.id:<{id_w}}  {icon}    "
            f"{_fmt_lat(r):>7}  {_fmt_tokens(r):>18}  {_fmt_calls(r):>5}  {_fmt_cost(r):>12}"
        )
        if not r.passed and r.fail_reason:
            indent = " " * (id_w + 12)
            print(f"{indent}↳ {r.fail_reason}")

    # Summary
    total_in = sum(r.input_tokens or 0 for r in results)
    total_out = sum(r.output_tokens or 0 for r in results)
    total_cost = sum(r.cost_usd or 0.0 for r in results)
    avg_lat = sum(r.latency_s for r in results) / total if total else 0.0

    print()
    print("  " + "─" * 60)
    print(
        f"  SUMMARY  {passed}/{total} passed"
        f"  |  tokens: {total_in}↑ {total_out}↓"
        f"  |  cost: ${total_cost:.6f}"
        f"  |  avg latency: {avg_lat:.1f}s"
    )
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

async def _main(base_url: str) -> int:
    print(f"Running eval against {base_url} …")
    results = await run_eval(base_url=base_url)
    print_report(results)
    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run project_agent eval suite")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.base_url)))


if __name__ == "__main__":
    main()
