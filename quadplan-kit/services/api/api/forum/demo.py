"""`make seed-forum-demo`: FAKE instructors and forum pages for local development.

The seed has no schedule data, so no `course_instructor` rows and no forum pages. This command
adds clearly fake instructors ("Demo Instructor A", slug `demo-instructor-a`, department
"Demo data (fake)") on a few real 2026-27 courses, plus a handful of fake posts, so the forum
can be tried locally. None of it is a catalog fact; it never goes into `data/seed`, and the
command refuses to run unless ENVIRONMENT=development. `--remove` deletes all of it.

Demo posts are written by made-up authors (random ids that match no account), so they belong
to nobody and account deletion never touches them.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from api.auth.hashing import author_ref
from api.config import get_settings
from api.db import models as m
from api.forum.pages import ensure_page
from api.forum.pseudonyms import pseudonym_for

DEMO_DEPARTMENT = "Demo data (fake)"
DEMO_SLUG_PREFIX = "demo-instructor-"
DEMO_TERM = "2026-AU"

#: (letter, course codes). Instructor names are invented; the courses are real seed courses.
DEMO_INSTRUCTORS: list[tuple[str, list[str]]] = [
    ("A", ["CMSC 14100", "CMSC 14200"]),
    ("B", ["CMSC 14100"]),
    ("C", ["MATH 15100"]),
    ("D", ["ECON 20000"]),
    ("E", ["HUMA 11000"]),
]

#: Fake reviews on CMSC 14100 with Demo Instructor A: (overall, difficulty, intensity,
#: workload, recommend, body).
DEMO_REVIEWS = [
    (5, 3, 4, 9.0, True, "Demo review (fake data). Clear lectures and weekly problem sets."),
    (4, 4, 4, 12.0, True, "Demo review (fake data). Start the projects early; office hours help."),
    (3, 3, 3, 8.0, False, "Demo review (fake data). Fine, but the pace felt slow at first."),
]
DEMO_DISCUSSION = (
    "Demo question (fake data): is the midterm curved?",
    "This is a fake discussion post for trying the forum locally.",
    [
        "Demo reply (fake data): it was last time, according to the syllabus.",
        "Demo reply (fake data): check the course page on Canvas.",
    ],
)


class DemoRefusedError(RuntimeError):
    pass


def _check_environment() -> None:
    if get_settings().environment != "development":
        raise DemoRefusedError(
            "seed-forum-demo adds fake instructors and posts; it runs only with "
            "ENVIRONMENT=development"
        )


def _latest_course(db: Session, code: str) -> m.Course | None:
    return db.scalar(
        sa.select(m.Course).where(m.Course.code == code).order_by(m.Course.catalog_year.desc())
    )


def remove_demo(db: Session) -> int:
    _check_environment()
    ids = list(
        db.scalars(sa.select(m.Instructor.id).where(m.Instructor.slug.startswith(DEMO_SLUG_PREFIX)))
    )
    if ids:
        # Pages (and their posts, pseudonyms and comments) cascade with the instructor.
        db.execute(sa.delete(m.Instructor).where(m.Instructor.id.in_(ids)))
    db.commit()
    return len(ids)


def seed_demo(db: Session) -> dict[str, int]:
    _check_environment()
    term = DEMO_TERM if db.get(m.Term, DEMO_TERM) is not None else None
    counts = {"instructors": 0, "pages": 0, "posts": 0, "skipped_courses": 0}
    first_page: m.CourseInstructor | None = None
    for letter, codes in DEMO_INSTRUCTORS:
        slug = f"{DEMO_SLUG_PREFIX}{letter.lower()}"
        instructor = db.scalar(sa.select(m.Instructor).where(m.Instructor.slug == slug))
        if instructor is None:
            instructor = m.Instructor(
                slug=slug,
                display_name=f"Demo Instructor {letter}",
                department=DEMO_DEPARTMENT,
                aliases=["fake", "demo"],
            )
            db.add(instructor)
            db.flush()
            counts["instructors"] += 1
        for code in codes:
            course = _latest_course(db, code)
            if course is None:
                counts["skipped_courses"] += 1
                continue
            page = ensure_page(db, course.id, instructor.id, term)
            counts["pages"] += 1
            if first_page is None:
                first_page = page
    if first_page is not None:
        has_posts = db.scalar(
            sa.select(sa.exists().where(m.Post.course_instructor_id == first_page.id))
        )
        if not has_posts:
            counts["posts"] = _demo_posts(db, first_page, term)
    db.commit()
    return counts


def _fake_author(page_id: int) -> str:
    return author_ref(uuid.uuid4(), page_id)  # a random id: matches no account


def _demo_posts(db: Session, page: m.CourseInstructor, term: str | None) -> int:
    n = 0
    for overall, difficulty, intensity, workload, recommend, body in DEMO_REVIEWS:
        ref = _fake_author(page.id)
        pseudonym = pseudonym_for(db, ref, page.id)
        post = m.Post(
            course_instructor_id=page.id,
            kind="review",
            author_ref=ref,
            pseudonym_id=pseudonym.id,
            body_md=body,
            term_taken=term,
            status="visible",
            score=overall - 2,
        )
        db.add(post)
        db.flush()
        db.add(
            m.ReviewRating(
                post_id=post.id,
                overall=overall,
                difficulty=difficulty,
                intellectual_intensity=intensity,
                workload_hours=workload,
                would_recommend=recommend,
            )
        )
        n += 1
    title, body, replies = DEMO_DISCUSSION
    ref = _fake_author(page.id)
    post = m.Post(
        course_instructor_id=page.id,
        kind="discussion",
        author_ref=ref,
        pseudonym_id=pseudonym_for(db, ref, page.id).id,
        title=title,
        body_md=body,
        status="visible",
    )
    db.add(post)
    db.flush()
    parent_path: str | None = None
    parent_id: int | None = None
    for text in replies:
        ref = _fake_author(page.id)
        new_id = int(
            db.scalar(sa.select(sa.func.nextval(sa.func.pg_get_serial_sequence("comment", "id"))))
            or 0
        )
        path = f"{parent_path}.{new_id}" if parent_path else str(new_id)
        db.add(
            m.Comment(
                id=new_id,
                post_id=post.id,
                parent_id=parent_id,
                path=path,
                author_ref=ref,
                pseudonym_id=pseudonym_for(db, ref, page.id).id,
                body_md=text,
                status="visible",
            )
        )
        db.flush()
        parent_path, parent_id = path, new_id
    return n + 1
