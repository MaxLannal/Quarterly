"""Benchmark from prompt 02: 60 courses, 200 nodes, 3 programs must verify in under 300 ms.
The timing is printed in pytest's summary (see conftest.py)."""

import statistics
import time
from typing import Any

from core_support import BENCHMARK, T, catalog, college, plan, program, ruleset
from planner_core import check_certificate, verify
from planner_core.dsl import iter_nodes
from planner_core.models import Catalog, PlanState, RuleSet

SUBJECTS = ("AAA", "BBB", "CCC")
BUDGET_MS = 300.0
SHARE_MAX = 26


def code(subject: str, i: int) -> str:
    return f"{subject} {20000 + 100 * i}"


def big_program(k: int) -> Any:
    """67 nodes: core slots, four tracks (one needed), electives, breadth, a bounded_parts."""
    mine, other, third = SUBJECTS[k], SUBJECTS[(k + 1) % 3], SUBJECTS[(k + 2) % 3]

    def slots(codes: list[str]) -> list[dict[str, Any]]:
        return [{"slot": {"any_of": [c]}} for c in codes]

    def pick(subject: str, low: int, high: int, count: int = 1) -> dict[str, Any]:
        number_range = [20000 + 100 * low, 20000 + 100 * high]
        return {
            "select": {"count": count, "from": {"subject": subject, "number_range": number_range}}
        }

    tracks = [
        {
            "id": f"t{t}",
            "group": {
                "all": True,
                "children": slots([code(mine, 10 + (t + j) % 6) for j in range(5)]),
            },
        }
        for t in range(4)
    ]
    children = [
        {
            "id": "core",
            "group": {"all": True, "children": slots([code(mine, i) for i in range(10)])},
        },
        {"id": "tracks", "group": {"n_of": 1, "children": tracks}},
        {
            "id": "electives",
            "group": {"all": True, "children": [pick(mine, 10 + i, 19) for i in range(4)]},
        },
        {
            "id": "breadth",
            "group": {"n_of": 10, "children": [pick(other, i, i + 6) for i in range(14)]},
            "constraints": {
                "max_from": {"selector": {"subject": other, "number_range": [20000, 20500]}, "n": 6}
            },
        },
        {
            "id": "extra",
            "group": {"all": True, "children": [pick(third, 2 * i, 2 * i + 5) for i in range(8)]},
        },
        {
            "id": "parts",
            "bounded_parts": {
                "total": {"courses": 4},
                "parts": [
                    {
                        "id": "a",
                        "from": {"subject": third, "number_range": [20000, 20900]},
                        "count": [1, 3],
                    },
                    {
                        "id": "b",
                        "from": {"subject": third, "number_range": [21000, 21900]},
                        "count": [1, 3],
                    },
                ],
            },
        },
    ]
    share = [
        {"with": f"program:p{(k + 1) % 3}", "max": SHARE_MAX},
        {"with": f"program:p{(k + 2) % 3}", "max": SHARE_MAX},
    ]
    return program(f"p{k}", {"group": {"all": True, "children": children}}, policy={"share": share})


def world(courses_per_subject: int = 20) -> tuple[PlanState, RuleSet, Catalog]:
    codes = [code(s, i) for s in SUBJECTS for i in range(courses_per_subject)]
    prereqs = {
        code(s, i): code(s, i - 4) for s in SUBJECTS for i in range(4, courses_per_subject, 2)
    }
    policy = college(
        full_time_min_units=300,
        full_time_max_units=500,
        total_units=6000,
        units_by_enrollment=5000,
        core_program_id="p0",
    )
    rules = ruleset(*[big_program(k) for k in range(3)], college=policy, prereqs=prereqs)
    # 60 courses over 12 quarters, 5 per quarter, each subject in catalog order
    order = [code(s, i) for i in range(courses_per_subject) for s in SUBJECTS]
    items = {T[q]: order[5 * q : 5 * q + 5] for q in range(12)}
    p = plan(items, programs=["p0", "p1", "p2"])
    return p, rules, catalog(codes)


def timed(p: PlanState, rules: RuleSet, cat: Catalog, rounds: int = 7) -> tuple[Any, float]:
    verify(p, rules, cat)  # warm-up (imports, solver start)
    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        report = verify(p, rules, cat)
        times.append((time.perf_counter() - start) * 1000)
    return report, statistics.median(times)


def test_benchmark_60_courses_200_nodes_3_programs() -> None:
    p, rules, cat = world()
    assert len(p.items) == 60 and len(rules.programs) == 3
    assert sum(1 for program in rules.programs for _ in iter_nodes(program)) >= 200
    report, ms = timed(p, rules, cat)
    BENCHMARK["verify, 60 courses / 201 nodes / 3 programs, satisfied"] = ms
    print(f"benchmark: verify (satisfied plan) median {ms:.1f} ms")
    assert report.certificate is not None, [i.message for i in report.issues if i.level == "error"]
    assert check_certificate(p, rules, cat, report.certificate)
    assert ms < BUDGET_MS

    start = time.perf_counter()
    assert check_certificate(p, rules, cat, report.certificate)
    BENCHMARK["check_certificate, same plan"] = (time.perf_counter() - start) * 1000

    # an incomplete plan needs the second (best-effort) solve: still within budget, and
    # the unmet set is proven minimal (no work-limit note)
    short = p.model_copy(update={"items": p.items[:50]})
    report, ms = timed(short, rules, cat)
    BENCHMARK["verify, 50 of the 60 courses, unsatisfied (two solves)"] = ms
    print(f"benchmark: verify (unsatisfied plan) median {ms:.1f} ms")
    assert report.status == "errors" and ms < BUDGET_MS
    assert any(i.code == "V07" for i in report.issues)
    assert not any("work limit" in note for note in report.assumptions)
