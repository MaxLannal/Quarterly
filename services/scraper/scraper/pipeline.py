"""The quarterly schedule pipeline run (SPEC "Quarterly schedule pipeline", steps 2-3):
stored snapshots -> parse -> checks -> `section`, `instructor`, `course_instructor` (forum
pages, via `api.forum.pages.ensure_page`) and `offering_pattern`.

Every run is recorded as one `extraction_run` row (`kind = "schedule_parse"`, model
`deterministic`) with its snapshot ids, the parser version and the counts, so it can be
reviewed and so the self-repair agent knows the last good counts. Anything uncertain becomes a
`review_item`: unknown course codes, uncertain instructor matches and count alerts. A failed
parse writes nothing but the failed run row.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

import api.db.models as m
import sqlalchemy as sa
from api.forum.pages import ensure_page
from planner_core.terms import parse_term
from sqlalchemy.orm import Session

from scraper import review
from scraper.checks import (
    CountCheck,
    KnownInstructor,
    match_name,
    normalize_name,
    same_quarter_last_year,
)
from scraper.offering import update_from_posted_schedule
from scraper.parse import DEFAULT_CONFIG, ParsedSection, ParseError, ParserConfig, parse_page
from scraper.snapshots import SnapshotStore, read_snapshot

RUN_KIND = "schedule_parse"
NOT_LISTED = "not_listed"  # a section that disappeared from a later run of the same term


@dataclass
class RunReport:
    run_id: int
    status: Literal["ok", "failed"]
    term_id: str
    snapshot_ids: list[int]
    parser_version: str
    counts_by_subject: dict[str, int] = field(default_factory=dict)
    counts_by_snapshot: dict[int, int] = field(default_factory=dict)
    sections_written: int = 0
    sections_unlisted: int = 0
    pages_created: int = 0
    new_instructors: list[str] = field(default_factory=list)
    review_item_ids: list[int] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def output(self) -> dict[str, Any]:
        return {
            "term_id": self.term_id,
            "parser_version": self.parser_version,
            "snapshot_ids": self.snapshot_ids,
            "counts_by_subject": self.counts_by_subject,
            # JSON keys are strings
            "counts_by_snapshot": {str(k): v for k, v in self.counts_by_snapshot.items()},
            "sections_written": self.sections_written,
            "sections_unlisted": self.sections_unlisted,
            "pages_created": self.pages_created,
            "new_instructors": self.new_instructors,
            "review_item_ids": self.review_item_ids,
            "errors": self.errors,
        }


def active_config(db: Session) -> ParserConfig:
    """The parser selectors in use: the newest *accepted* repair proposal, else the default.
    A proposal changes the parser only after a curator accepts its review item."""
    item = db.scalar(
        sa.select(m.ReviewItem)
        .where(m.ReviewItem.target_type == review.PARSER_REPAIR, m.ReviewItem.status == "accepted")
        .order_by(m.ReviewItem.id.desc())
        .limit(1)
    )
    proposal = (item.diff or {}).get("proposed_config") if item is not None else None
    return ParserConfig.model_validate(proposal) if proposal else DEFAULT_CONFIG


def ensure_term(db: Session, term_id: str) -> None:
    if db.get(m.Term, term_id) is None:
        year, quarter = parse_term(term_id)
        db.add(m.Term(id=term_id, year=year, quarter=quarter))
        db.flush()


def instructor_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", normalize_name(name)).strip("-")[:100] or "instructor"
    slug, n = base, 1
    while db.scalar(sa.select(m.Instructor.id).where(m.Instructor.slug == slug)) is not None:
        n += 1
        slug = f"{base}-{n}"
    return slug


def _section_ref(s: ParsedSection) -> dict[str, Any]:
    return {"course": s.course_code, "section": s.section_no, "component": s.component}


def parse_snapshots(
    db: Session, store: SnapshotStore, snapshot_ids: list[int], config: ParserConfig
) -> tuple[list[tuple[int, dt.datetime, ParsedSection]], dict[int, int], list[dict[str, Any]]]:
    """(snapshot id, fetched at, section) for every section; counts per snapshot; errors."""
    sections: list[tuple[int, dt.datetime, ParsedSection]] = []
    counts: dict[int, int] = {}
    errors: list[dict[str, Any]] = []
    for sid in snapshot_ids:
        try:
            snap, html = read_snapshot(db, store, sid)
            parsed = parse_page(html, config)
        except (ParseError, LookupError, ValueError, KeyError) as exc:
            errors.append({"snapshot_id": sid, "error": f"{type(exc).__name__}: {exc}"[:500]})
            continue
        counts[sid] = len(parsed)
        sections.extend((sid, snap.fetched_at, s) for s in parsed)
    return sections, counts, errors


def run_schedule(
    db: Session,
    store: SnapshotStore,
    term_id: str,
    snapshot_ids: list[int],
    *,
    config: ParserConfig | None = None,
) -> RunReport:
    """One reviewable pipeline run over stored snapshots of `term_id`. The caller commits."""
    config = config or active_config(db)
    ensure_term(db, term_id)
    run = m.ExtractionRun(
        kind=RUN_KIND,
        model="deterministic",
        prompt_version=config.version,
        input_snapshot_ids=list(snapshot_ids),
        status="running",
        cost_usd=0,
    )
    db.add(run)
    db.flush()
    report = RunReport(run.id, "ok", term_id, list(snapshot_ids), config.version)

    parsed, report.counts_by_snapshot, report.errors = parse_snapshots(
        db, store, snapshot_ids, config
    )
    if not parsed and not report.errors:
        report.errors.append({"snapshot_id": None, "error": "the run parsed zero sections"})
    if report.errors:
        # Nothing is written from a run that did not parse cleanly (self-repair takes over).
        report.status = "failed"
        run.status = "failed"
        run.output = report.output()
        db.flush()
        return report

    # ---- unknown course codes
    codes = sorted({s.course_code for _, _, s in parsed})
    course_ids: dict[str, int] = {}
    for code in codes:
        cid = db.scalar(
            sa.select(m.Course.id)
            .where(m.Course.code == code)
            .order_by(m.Course.catalog_year.desc())
        )
        if cid is not None:
            course_ids[code] = cid
            continue
        listed = [(sid, s) for sid, _, s in parsed if s.course_code == code]
        item = review.open_review(
            db,
            review.UNKNOWN_CODE,
            f"{term_id}:{code}",
            {
                "term_id": term_id,
                "course_code": code,
                "sections": [_section_ref(s) for _, s in listed],
                "snapshot_ids": sorted({sid for sid, _ in listed}),
                "run_id": run.id,
            },
            f"{code} is on the {term_id} schedule but not in the catalog (a new or topics "
            "course?). Its sections were not saved.",
        )
        report.review_item_ids.append(item.id)
    known_sections = [(sid, at, s) for sid, at, s in parsed if s.course_code in course_ids]

    # ---- instructor names
    known = [
        KnownInstructor(i.id, i.display_name, tuple(i.aliases))
        for i in db.scalars(sa.select(m.Instructor).order_by(m.Instructor.id))
    ]
    name_ids: dict[str, int | None] = {}
    uncertain: dict[str, list[ParsedSection]] = {}
    candidates: dict[str, tuple[tuple[int, str, float], ...]] = {}
    for _, _, s in known_sections:
        for name in s.instructors:
            if name in name_ids:
                if name_ids[name] is None:
                    uncertain[name].append(s)
                continue
            match = match_name(name, known)
            if match.outcome == "matched":
                name_ids[name] = match.instructor_id
            elif match.outcome == "new":
                person = m.Instructor(
                    slug=instructor_slug(db, name),
                    display_name=name,
                    department=s.subject,
                    aliases=[],
                )
                db.add(person)
                db.flush()
                known.append(KnownInstructor(person.id, name))
                name_ids[name] = person.id
                report.new_instructors.append(name)
            else:
                name_ids[name] = None
                uncertain[name] = [s]
                candidates[name] = match.candidates
    for name, rows in uncertain.items():
        item = review.open_review(
            db,
            review.INSTRUCTOR_MATCH,
            f"{term_id}:{normalize_name(name)}",
            {
                "term_id": term_id,
                "name": name,
                "candidates": [
                    {"instructor_id": i, "display_name": n, "score": sc}
                    for i, n, sc in candidates[name]
                ],
                "sections": [_section_ref(s) for s in rows],
                "run_id": run.id,
            },
            f'"{name}" looks like an existing instructor but is not an exact match. Pick the '
            "same person, or mark them as new. Until then these sections show no instructor "
            "under this name.",
        )
        report.review_item_ids.append(item.id)

    # ---- section counts against the same quarter last year
    by_subject = Counter(s.subject for _, _, s in known_sections)
    report.counts_by_subject = dict(sorted(by_subject.items()))
    last_year = same_quarter_last_year(term_id)
    for subject, count in sorted(by_subject.items()):
        baseline = db.scalar(
            sa.select(sa.func.count())
            .select_from(m.Section)
            .join(m.Course, m.Course.id == m.Section.course_id)
            .where(
                m.Section.term_id == last_year,
                m.Course.subject == subject,
                m.Section.status.is_distinct_from(NOT_LISTED),
            )
        )
        check = CountCheck(subject, count, baseline or None, last_year)
        if check.alert:
            change = check.change or 0.0
            item = review.open_review(
                db,
                review.COUNT_ALERT,
                f"{term_id}:{subject}",
                {
                    "term_id": term_id,
                    "subject": subject,
                    "count": count,
                    "baseline": check.baseline,
                    "baseline_term": last_year,
                    "change": round(change, 3),
                    "run_id": run.id,
                    "snapshot_ids": list(snapshot_ids),
                },
                f"{subject} has {count} sections in {term_id} against {check.baseline} in "
                f"{last_year} ({change:+.0%}, more than +/-30%). The page layout may have "
                "changed, or pages may be missing. The sections were saved; check them.",
            )
            report.review_item_ids.append(item.id)

    # ---- sections (upsert by course, section number and component)
    subjects = set(by_subject)
    existing = {
        (row.course_id, row.section_no, row.component): row
        for row in db.scalars(
            sa.select(m.Section)
            .join(m.Course, m.Course.id == m.Section.course_id)
            .where(m.Section.term_id == term_id, m.Course.subject.in_(subjects))
        )
    }
    seen: set[tuple[int, str, str | None]] = set()
    written: list[tuple[int, m.Section]] = []
    for sid, fetched_at, s in known_sections:
        key = (course_ids[s.course_code], s.section_no, s.component)
        seen.add(key)
        row = existing.get(key)
        if row is None:
            row = m.Section(
                term_id=term_id,
                course_id=key[0],
                section_no=s.section_no,
                component=s.component,
            )
            db.add(row)
        row.instructor_ids = [i for n in s.instructors if (i := name_ids.get(n)) is not None]
        row.meetings = [dict(x) for x in s.meetings]
        row.capacity = s.capacity
        row.status = s.status
        row.source_id = sid
        row.scraped_at = fetched_at
        written.append((key[0], row))
    for key, row in existing.items():
        if key not in seen and row.status != NOT_LISTED:
            row.status = NOT_LISTED
            report.sections_unlisted += 1
    db.flush()
    report.sections_written = len(written)

    # ---- forum pages (one per course x instructor, cross-listings share a page)
    pages_before = db.scalar(sa.select(sa.func.count()).select_from(m.CourseInstructor)) or 0
    for course_id, row in written:
        if row.status == "cancelled":
            continue
        for instructor_id in row.instructor_ids:
            ensure_page(db, course_id, instructor_id, term_id)
    pages_after = db.scalar(sa.select(sa.func.count()).select_from(m.CourseInstructor)) or 0
    report.pages_created = pages_after - pages_before

    # ---- offering patterns (a posted schedule: p = 1)
    update_from_posted_schedule(db, term_id, subjects)

    run.status = "ok"
    run.output = report.output()
    db.flush()
    return report
