"""The student's standards that the planner checks itself, on top of Quarterly's verifier
(plan-guideline G14-G16): no course in a quarter away (S01), no quarter above the chosen course
load (S02), no course from the "do not want" list (S03). A break goes back to the repair step.

The "do not want" list is the course codes on working-information lines of kind `avoid`, which
the chat tool `note_preference` writes as `- YYYY-MM-DD · avoid · <text> [CODE, CODE]`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from planner_core.models import Catalog, PlanState

from api.agents.live import normalize_code
from api.schemas.planner import PlanIssue

PREFERENCE_KINDS = ("avoid", "prefer", "schedule", "other")
_LINE = re.compile(r"^- \d{4}-\d{2}-\d{2} · (\w+) · .*?(?: \[([^\]]*)\])?\s*$")
#: Course load -> most units in one quarter (data/profile/questions.yaml: "Normal: a mix of
#: 300-unit and 400-unit quarters"; "Ambitious: ... 500 units ... when the College approves an
#: overload", which the verifier's V05 already checks).
MAX_UNITS = {"conservative": 400, "normal": 400}
DEFAULT_UNITS = 100


@dataclass(frozen=True)
class Standards:
    away_terms: frozenset[str]
    max_units: int | None
    avoid: frozenset[str]


def preference_line(day: dt.date, kind: str, text: str, courses: list[str]) -> str:
    """One working-information line, as `note_preference` writes it."""
    clean = " ".join(text.split())
    codes = [c for c in (normalize_code(x) for x in courses) if c]
    tail = f" [{', '.join(dict.fromkeys(codes))}]" if codes else ""
    return f"- {day.isoformat()} · {kind} · {clean}{tail}"


def avoided_courses(working_notes: str | None) -> frozenset[str]:
    out: set[str] = set()
    for line in (working_notes or "").splitlines():
        m = _LINE.match(line.strip())
        if m and m.group(1) == "avoid" and m.group(2):
            out |= {c for c in (normalize_code(x) for x in m.group(2).split(",")) if c}
    return frozenset(out)


def standards_from(record: Mapping[str, Any], working_notes: str | None) -> Standards:
    """`record` = the General Information answers (the saved record, or a browser plan's
    answers)."""
    away = frozenset(
        str(t["term"]) for t in record.get("terms_away") or [] if isinstance(t, Mapping)
    )
    load = record.get("course_load")
    return Standards(
        away_terms=away,
        max_units=MAX_UNITS.get(load) if isinstance(load, str) else None,
        avoid=avoided_courses(working_notes),
    )


def standard_issues(state: PlanState, catalog: Catalog, standards: Standards) -> list[PlanIssue]:
    """Errors for the planned courses that break a standard (completed courses are history)."""
    units_of = {c.code: c.units for c in catalog.courses}
    planned = [i for i in state.items or [] if i.course and i.status != "completed"]
    issues: list[PlanIssue] = []

    away = [i for i in planned if i.term in standards.away_terms]
    for term in sorted({i.term for i in away}):
        codes = [i.course for i in away if i.term == term and i.course]
        issues.append(
            PlanIssue(
                code="S01",
                level="error",
                message=f"{', '.join(codes)} is planned in {term}, a quarter you are away.",
                course_ids=codes,
                term_ids=[term],
            )
        )

    if standards.max_units is not None:
        load: dict[str, int] = defaultdict(int)
        for i in planned:
            assert i.course is not None
            units = i.units if i.units is not None else units_of.get(i.course)
            load[i.term] += units if units is not None else DEFAULT_UNITS
        for term in sorted(t for t, u in load.items() if u > standards.max_units):
            issues.append(
                PlanIssue(
                    code="S02",
                    level="error",
                    message=(
                        f"{term} has {load[term]} units; your course load allows "
                        f"{standards.max_units}."
                    ),
                    term_ids=[term],
                )
            )

    for i in planned:
        if i.course in standards.avoid:
            issues.append(
                PlanIssue(
                    code="S03",
                    level="error",
                    message=f"You said you do not want {i.course}.",
                    course_ids=[i.course],
                    term_ids=[i.term],
                )
            )
    return issues
