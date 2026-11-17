"""Tables for docs/LIVE-TEST-REPORT.md from evals/live/results.jsonl and ledger.jsonl.

    uv run python evals/live/report_table.py > /tmp/tables.md

No API calls: it only reads the files the live run wrote.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

LIVE = Path(__file__).resolve().parent


def rows(name: str) -> list[dict[str, Any]]:
    path = LIVE / name
    return (
        [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if path.exists()
        else []
    )


def main() -> None:
    results = rows("results.jsonl")
    ledger = rows("ledger.jsonl")
    # The last result per test id (a phase 5 re-run has its own "-rerun" id).
    last: dict[str, dict[str, Any]] = {}
    for r in results:
        last[r["test_id"]] = r
    print(
        "| Test id | Phase | Model | Result | Tokens in / out (cache read / write) | Cost | Latency |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in last.values():
        tokens = f"{r['input_tokens']} / {r['output_tokens']} ({r['cache_read_tokens']} / {r['cache_write_tokens']})"
        print(
            f"| `{r['test_id']}` | {r['phase'][-1]} | {r['model']} | {r['result']} | {tokens} | ${r['cost_usd']:.4f} | {r['latency_s']} s |"
        )
    print()
    by_phase: dict[str, float] = defaultdict(float)
    for e in ledger:
        by_phase[e["phase"]] += e["cost_usd"]
    total = sum(by_phase.values())
    print(
        f"Ledger: {len(ledger)} calls, total ${total:.4f}; "
        + ", ".join(f"{p} ${v:.4f}" for p, v in sorted(by_phase.items()))
    )
    print()
    tasks: dict[str, list[float]] = defaultdict(list)
    for e in ledger:
        tasks[e["task"] or "(smoke)"].append(e["cost_usd"])
    print("| Task | Calls | Mean cost per call |")
    print("| --- | --- | --- |")
    for task, costs in sorted(tasks.items()):
        print(f"| {task} | {len(costs)} | ${mean(costs):.5f} |")
    print()

    def per_test(prefix: str, model: str | None = None) -> list[float]:
        return [
            r["cost_usd"]
            for r in last.values()
            if r["test_id"].startswith(prefix)
            and r["result"] != "not run (budget)"
            and (model is None or r["model"] == model)
        ]

    for label, prefix, model in (
        ("plan generation, Sonnet 5.5", "a1-p", "claude-sonnet-5-5"),
        ("plan generation, Opus 5.5", "a1-p", "claude-opus-5-5"),
        ("chat message (in scope)", "p3-in-", None),
        ("off-topic message (classifier only)", "p3-off-", None),
        ("forum post moderated (A4)", "p4-a4-", "claude-haiku-5-5"),
        ("summary (A3, with its moderation)", "p4-a3s-", None),
    ):
        costs = [c for c in per_test(prefix, model) if c > 0]
        if costs:
            print(
                f"- {label}: mean ${mean(costs):.4f} over {len(costs)} runs (min ${min(costs):.4f}, max ${max(costs):.4f})"
            )


if __name__ == "__main__":
    main()
