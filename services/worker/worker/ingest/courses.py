"""Course blocks -> staged `course`, `crosslist_group` and `course_relation` rows (code only,
SPEC "Annual catalog pipeline" step 2), and the per-subject diff a curator reviews.

- `Equivalent Course(s)` lists cross-listings: codes that count as one course.
- Relations come only from fixed sentence patterns, each kept with its sentence:
  "credit for both X and Y" / "credit for only one of X and Y" -> `mutually_exclusive`,
  "replaces X" / "formerly X" -> `replaces`. Anything else stays in the text.
- Nothing is applied: each subject becomes one `course_batch` review item listing what was
  added, changed and removed against last year. Accepting it writes the rows.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from worker.ingest import courseleaf
from worker.ingest.catalog import CourseFacts
from worker.ingest.records import ReviewDraft
from worker.ingest.snapshots import Snapshot

_CODE = r"([A-Z]{2,5} \d{5})"
EXCLUSIVE = [
    re.compile(rf"[^.]*credit for both {_CODE} and {_CODE}[^.]*\."),
    re.compile(rf"[^.]*credit for only one of {_CODE} (?:and|or) {_CODE}[^.]*\."),
]
REPLACES = re.compile(rf"[^.]*\b(?:replaces|formerly) {_CODE}[^.]*\.", re.IGNORECASE)


@dataclass
class StagedCourse:
    code: str
    subject: str
    number: str
    title: str
    units: int
    description: str | None
    notes: str | None
    prereq_text: str | None
    terms_offered: list[str]
    crosslists: list[str]
    source: dict[str, str]  # {snapshot_id, url, quote}

    def comparable(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("source")
        data["crosslists"] = sorted(self.crosslists)
        return data


@dataclass
class StagedRelation:
    a: str
    b: str
    kind: str
    source: dict[str, str]


@dataclass
class StagedCatalog:
    catalog_year: str
    courses: dict[str, StagedCourse] = field(default_factory=dict)
    crosslist_groups: list[list[str]] = field(default_factory=list)
    relations: list[StagedRelation] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def facts(self) -> list[CourseFacts]:
        return [
            CourseFacts(c.code, c.title, c.units, tuple(c.crosslists))
            for c in self.courses.values()
        ]


def _groups(courses: dict[str, StagedCourse]) -> list[list[str]]:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for course in courses.values():
        for other in course.crosslists:
            if other in courses:
                parent[find(course.code)] = find(other)
    groups: dict[str, set[str]] = {}
    for code in list(parent):
        groups.setdefault(find(code), set()).add(code)
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


def _relations(course: StagedCourse) -> list[StagedRelation]:
    text = " ".join(t for t in (course.description, course.notes) if t)
    out: list[StagedRelation] = []
    for pattern in EXCLUSIVE:
        for match in pattern.finditer(text):
            a, b = sorted((match.group(1), match.group(2)))
            out.append(
                StagedRelation(
                    a, b, "mutually_exclusive", {**course.source, "quote": match.group(0).strip()}
                )
            )
    for match in REPLACES.finditer(text):
        out.append(
            StagedRelation(
                course.code,
                match.group(1),
                "replaces",
                {**course.source, "quote": match.group(0).strip()},
            )
        )
    return out


def parse_courses(catalog_year: str, pages: Iterable[Snapshot]) -> StagedCatalog:
    staged = StagedCatalog(catalog_year=catalog_year)
    for snap in pages:
        blocks, problems = courseleaf.course_blocks(snap.text())
        staged.problems += [f"{snap.url}: {p}" for p in problems]
        for block in blocks:
            details = block.details
            course = StagedCourse(
                code=block.code,
                subject=block.subject,
                number=block.number,
                title=block.title,
                units=block.units,
                description=block.description,
                notes=details.get("notes"),
                prereq_text=details.get("prerequisites"),
                terms_offered=courseleaf.quarters_of(details.get("terms_offered", "")),
                crosslists=[
                    c
                    for c in courseleaf.codes_in(details.get("equivalents", ""))
                    if c != block.code
                ],
                source={"snapshot_id": snap.id, "url": snap.url, "quote": block.title_line},
            )
            existing = staged.courses.get(course.code)
            if existing is None:
                staged.courses[course.code] = course
            elif existing.comparable() != course.comparable():
                staged.problems.append(
                    f"{course.code} appears on {existing.source['url']} and {snap.url} with "
                    "different text; the first one is kept"
                )
    for code, course in staged.courses.items():
        for other in course.crosslists:
            if other not in staged.courses:
                staged.problems.append(f"{code}: equivalent course {other} was not found")
    staged.crosslist_groups = _groups(staged.courses)
    seen: set[tuple[str, str, str]] = set()
    for course in staged.courses.values():
        for rel in _relations(course):
            key = (rel.a, rel.b, rel.kind)
            if key not in seen and rel.a in staged.courses and rel.b in staged.courses:
                seen.add(key)
                staged.relations.append(rel)
    return staged


# ------------------------------------------------------------------------------- diff


def course_batches(
    staged: StagedCatalog,
    previous: dict[str, dict[str, Any]],
    *,
    previous_year: str | None,
    requisites: dict[str, dict[str, Any]] | None = None,
) -> list[ReviewDraft]:
    """One `course_batch` review item per subject. `previous` maps a code to last year's
    comparable fields (`StagedCourse.comparable()` shape); `requisites` maps a code to the
    E1 result that passed its checks (applied with the batch)."""
    requisites = requisites or {}
    subjects = sorted(
        {c.subject for c in staged.courses.values()} | {k.split(" ")[0] for k in previous}
    )
    drafts = []
    for subject in subjects:
        now = {k: c for k, c in staged.courses.items() if c.subject == subject}
        before = {k: v for k, v in previous.items() if k.split(" ")[0] == subject}
        added = [asdict(now[k]) for k in sorted(set(now) - set(before))]
        removed = sorted(set(before) - set(now))
        changed = []
        for code in sorted(set(now) & set(before)):
            after = now[code].comparable()
            fields = sorted(k for k in after if after[k] != before[code].get(k))
            if fields:
                changed.append(
                    {"code": code, "fields": fields, "before": before[code], "after": after}
                )
        members = set(now)
        groups = [g for g in staged.crosslist_groups if members & set(g)]
        relations = [asdict(r) for r in staged.relations if r.a in members or r.b in members]
        unchanged = not (added or removed or changed)
        if unchanged:
            reason = (
                f"{subject}: no changes since {previous_year}; accept to carry the courses over"
            )
        else:
            reason = (
                f"{subject}: {len(added)} new, {len(changed)} changed, {len(removed)} removed"
                + (f" since {previous_year}" if previous_year else "")
            )
        drafts.append(
            ReviewDraft(
                target_type="course_batch",
                target_id=f"{staged.catalog_year}:{subject}",
                diff={
                    "kind": "course_batch",
                    "catalog_year": staged.catalog_year,
                    "previous_year": previous_year,
                    "subject": subject,
                    "unchanged": unchanged,
                    "courses": [asdict(c) for c in now.values()],
                    "added": [a["code"] for a in added],
                    "changed": changed,
                    "removed": removed,
                    "crosslist_groups": groups,
                    "relations": relations,
                    "requisites": {k: v for k, v in requisites.items() if k in members},
                },
                reason=reason,
            )
        )
    return drafts


def previous_from_db(session: Any, catalog_year: str) -> dict[str, dict[str, Any]]:
    """Last year's courses in `StagedCourse.comparable()` shape."""
    import sqlalchemy as sa
    from api.db import models as m

    rows = session.scalars(sa.select(m.Course).where(m.Course.catalog_year == catalog_year)).all()
    by_id = {r.id: r.code for r in rows}
    groups: dict[str, list[int]] = {}
    for g in session.scalars(
        sa.select(m.CrosslistGroup).where(m.CrosslistGroup.course_id.in_(list(by_id)))
    ):
        groups.setdefault(g.group_id, []).append(g.course_id)
    cross: dict[str, list[str]] = {}
    for members in groups.values():
        codes = [by_id[i] for i in members]
        for code in codes:
            cross[code] = sorted(c for c in codes if c != code)
    reqs = {
        r.course_id: r.raw_text
        for r in session.scalars(
            sa.select(m.Requisite).where(m.Requisite.catalog_year == catalog_year)
        )
    }
    offered = {
        (o.course_id, o.quarter)
        for o in session.scalars(
            sa.select(m.OfferingPattern).where(m.OfferingPattern.p_offered >= 0.5)
        )
    }
    out = {}
    for r in rows:
        out[r.code] = {
            "code": r.code,
            "subject": r.subject,
            "number": r.number,
            "title": r.title,
            "units": r.units,
            "description": r.description,
            "notes": r.notes,
            "prereq_text": reqs.get(r.id),
            "terms_offered": [q for q in ("AU", "WI", "SP", "SU") if (r.id, q) in offered],
            "crosslists": cross.get(r.code, []),
        }
    return out
