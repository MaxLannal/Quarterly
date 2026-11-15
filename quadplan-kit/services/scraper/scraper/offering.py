"""`offering_pattern` (SPEC "Predicting future offerings").

For quarter q and course c, with k = the number of the last 3 years in which c was offered
in q: p = (k + 1) / (3 + 2). A department's published plan sets p = 0.95; a posted schedule
sets p = 1. Precedence: posted schedule > department plan > history.

Courses are matched by code across catalog years (a section of last year's CMSC 14100 row
counts for this year's row); the pattern is stored on the newest course row of the code.
"""

from __future__ import annotations

from collections.abc import Collection

import api.db.models as m
import sqlalchemy as sa
from sqlalchemy.orm import Session

POSTED: float = 1.0
DEPARTMENT_PLAN: float = 0.95
YEARS = 3
#: Section statuses that do not count as the course being offered.
NOT_OFFERED = ("not_listed", "cancelled")


def history_p(k: int) -> float:
    if not 0 <= k <= YEARS:
        raise ValueError(f"k must be 0..{YEARS}, got {k}")
    return (k + 1) / (YEARS + 2)


def _terms(term_id: str) -> list[str]:
    """The same quarter in the last 3 years, this one included."""
    year, quarter = term_id.split("-")
    return [f"{int(year) - i}-{quarter}" for i in range(YEARS)]


def _upsert(
    db: Session, course_id: int, quarter: str, p: float, evidence: list[str], method: str
) -> m.OfferingPattern:
    row = db.scalar(
        sa.select(m.OfferingPattern).where(
            m.OfferingPattern.course_id == course_id, m.OfferingPattern.quarter == quarter
        )
    )
    if row is None:
        row = m.OfferingPattern(course_id=course_id, quarter=quarter)
        db.add(row)
    row.p_offered = p
    row.evidence_terms = evidence
    row.method = method
    return row


def newest_course_id(db: Session, code: str) -> int | None:
    return db.scalar(
        sa.select(m.Course.id).where(m.Course.code == code).order_by(m.Course.catalog_year.desc())
    )


def _offered_terms(db: Session, terms: list[str], codes: Collection[str] | None,
                   subjects: Collection[str] | None) -> dict[str, set[str]]:  # fmt: skip
    """code -> the terms among `terms` with a listed section."""
    stmt = (
        sa.select(m.Course.code, m.Section.term_id)
        .join(m.Course, m.Course.id == m.Section.course_id)
        .where(
            m.Section.term_id.in_(terms),
            sa.or_(m.Section.status.is_(None), m.Section.status.notin_(NOT_OFFERED)),
        )
        .distinct()
    )
    if codes is not None:
        stmt = stmt.where(m.Course.code.in_(codes))
    if subjects is not None:
        stmt = stmt.where(m.Course.subject.in_(subjects))
    out: dict[str, set[str]] = {}
    for code, term in db.execute(stmt):
        out.setdefault(code, set()).add(term)
    return out


def update_from_posted_schedule(db: Session, term_id: str, subjects: Collection[str]) -> int:
    """After a posted schedule for `term_id` was written for `subjects`: p = 1 for every
    course listed; for courses of those subjects offered in this quarter in the two years
    before but not now, p from history. Department-plan rows are left alone for courses not
    listed. Returns the number of rows written. The caller commits."""
    quarter = term_id.split("-")[1]
    window = _terms(term_id)
    offered = _offered_terms(db, window, None, subjects)
    # Courses whose sections this term were all dropped or cancelled: k counts no offering now.
    for code in db.scalars(
        sa.select(m.Course.code)
        .join(m.Section, m.Section.course_id == m.Course.id)
        .where(m.Section.term_id == term_id, m.Course.subject.in_(subjects))
        .distinct()
    ):
        offered.setdefault(code, set())
    written = 0
    for code, terms in sorted(offered.items()):
        course_id = newest_course_id(db, code)
        if course_id is None:
            continue
        evidence = sorted(terms)
        if term_id in terms:
            _upsert(db, course_id, quarter, POSTED, evidence, "posted_schedule")
        else:
            existing = db.scalar(
                sa.select(m.OfferingPattern.method).where(
                    m.OfferingPattern.course_id == course_id, m.OfferingPattern.quarter == quarter
                )
            )
            if existing == "department_plan":
                continue
            _upsert(db, course_id, quarter, history_p(len(terms)), evidence, "history")
        written += 1
    db.flush()
    return written


def apply_department_plan(db: Session, offerings: list[tuple[str, str]]) -> int:
    """p = 0.95 for each (code, planned term id) of an *accepted* department plan, unless the
    posted schedule of that same term already set p = 1. The plan's review item keeps the
    quotes and snapshot id. The caller commits."""
    written = 0
    for code, term_id in offerings:
        quarter = term_id.split("-")[1]
        course_id = newest_course_id(db, code)
        if course_id is None:
            continue
        row = db.scalar(
            sa.select(m.OfferingPattern).where(
                m.OfferingPattern.course_id == course_id, m.OfferingPattern.quarter == quarter
            )
        )
        if row is not None and row.method == "posted_schedule" and term_id in row.evidence_terms:
            continue
        _upsert(db, course_id, quarter, DEPARTMENT_PLAN, [term_id], "department_plan")
        written += 1
    db.flush()
    return written
