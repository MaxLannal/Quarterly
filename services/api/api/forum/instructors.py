"""Instructor directory and instructor page (SPEC "Instructor page"). Names, departments and
the courses taught are public (P03-12); per-course ratings and forum-derived attributes are
added only for logged-in readers."""

from __future__ import annotations

import sqlalchemy as sa
from planner_core.models import AttributeValue
from sqlalchemy.orm import Session

from api.db import models as m
from api.forum import pages
from api.repo.catalog import NotFoundError, _attribute
from api.schemas.catalog import InstructorCourse, InstructorDetail, InstructorSummary


def search(
    db: Session, q: str | None, *, limit: int, offset: int
) -> tuple[list[InstructorSummary], int]:
    stmt = sa.select(m.Instructor)
    if q and q.strip():
        like = f"%{q.strip().replace('%', '').replace('_', ' ')}%"
        stmt = stmt.where(
            sa.or_(
                m.Instructor.display_name.ilike(like),
                m.Instructor.slug.ilike(like.replace(" ", "-")),
                sa.func.array_to_string(m.Instructor.aliases, " ").ilike(like),
            )
        )
    total = db.scalar(sa.select(sa.func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(m.Instructor.display_name, m.Instructor.id).limit(limit).offset(offset)
    )
    return [pages.instructor_summary(r) for r in rows], total


def _page_attributes(db: Session, page_ids: list[int]) -> dict[int, list[AttributeValue]]:
    out: dict[int, list[AttributeValue]] = {pid: [] for pid in page_ids}
    if not page_ids:
        return out
    rows = db.scalars(
        sa.select(m.AttributeValue).where(
            m.AttributeValue.subject_type == "course_instructor",
            m.AttributeValue.subject_id.in_([str(p) for p in page_ids]),
        )
    )
    for row in rows:
        attribute = _attribute(row)
        out[int(row.subject_id)].append(
            attribute.model_copy(update={"subject_type": "course_instructor"})
        )
    return out


def detail(db: Session, slug: str, *, with_ratings: bool) -> InstructorDetail:
    row = db.scalar(sa.select(m.Instructor).where(m.Instructor.slug == slug))
    if row is None:
        raise NotFoundError(f"No instructor {slug}")
    taught = pages.instructor_pages(db, row.id)
    ids = [page.id for page, _ in taught]
    ratings = pages.ratings_by_page(db, ids) if with_ratings else {}
    attributes = _page_attributes(db, ids) if with_ratings else {}
    return InstructorDetail(
        **pages.instructor_summary(row).model_dump(),
        courses=[
            InstructorCourse(
                code=course.code,
                title=course.title,
                page_id=page.id,
                n_terms=page.n_terms,
                attributes=attributes.get(page.id, []),
                ratings=ratings.get(page.id),
            )
            for page, course in taught
        ],
    )
