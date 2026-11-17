"""What happens after a curator decides a schedule review item. These are called by the review
console (prompt 09) once an item is `accepted`; they refuse anything else, so an agent's or
scraper's output never takes effect without a person.

- `schedule_instructor_match`: the name is that existing instructor (becomes an alias), or a
  new instructor; their sections get the instructor and forum pages are created.
- `schedule_dept_plan`: the accepted offerings get p = 0.95.
- `schedule_parser_repair`: nothing to call; `pipeline.active_config` picks it up.
"""

from __future__ import annotations

import api.db.models as m
import sqlalchemy as sa
from api.forum.pages import ensure_page
from sqlalchemy.orm import Session

from scraper import review
from scraper.offering import apply_department_plan
from scraper.pipeline import instructor_slug


class NotAcceptedError(ValueError):
    pass


def _accepted(db: Session, item_id: int, kind: str) -> m.ReviewItem:
    item = db.get(m.ReviewItem, item_id)
    if item is None or item.target_type != kind:
        raise LookupError(f"no {kind} review item {item_id}")
    if item.status != "accepted":
        raise NotAcceptedError(f"review item {item_id} is {item.status}, not accepted")
    return item


def apply_instructor_match(db: Session, item_id: int, instructor_id: int | None) -> int:
    """`instructor_id` is the chosen existing instructor, or None for "a new person".
    Returns the instructor id. The caller commits."""
    item = _accepted(db, item_id, review.INSTRUCTOR_MATCH)
    name, term_id = item.diff["name"], item.diff["term_id"]
    if instructor_id is None:
        person = m.Instructor(slug=instructor_slug(db, name), display_name=name, aliases=[])
        db.add(person)
        db.flush()
    else:
        found = db.get(m.Instructor, instructor_id)
        if found is None:
            raise LookupError(f"no instructor {instructor_id}")
        person = found
        if name not in person.aliases and name != person.display_name:
            person.aliases = [*person.aliases, name]
    for ref in item.diff.get("sections", []):
        section = db.scalar(
            sa.select(m.Section)
            .join(m.Course, m.Course.id == m.Section.course_id)
            .where(
                m.Section.term_id == term_id,
                m.Course.code == ref["course"],
                m.Section.section_no == ref["section"],
                m.Section.component.is_not_distinct_from(ref["component"]),
            )
        )
        if section is None:
            continue
        if person.id not in section.instructor_ids:
            section.instructor_ids = [*section.instructor_ids, person.id]
        if section.status != "cancelled":
            ensure_page(db, section.course_id, person.id, term_id)
    db.flush()
    return person.id


def apply_department_plan_item(db: Session, item_id: int) -> int:
    """Set p = 0.95 for the accepted offerings of a department plan. Returns rows written."""
    item = _accepted(db, item_id, review.DEPT_PLAN)
    offerings = [
        (row["course_code"], term) for row in item.diff.get("accepted", []) for term in row["terms"]
    ]
    return apply_department_plan(db, offerings)
