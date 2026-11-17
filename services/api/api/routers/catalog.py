from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from planner_core.models import CourseList, ProgramType, Quarter, Term
from sqlalchemy.orm import Session

from api.auth.sessions import SessionData, optional_session
from api.config import get_settings
from api.db.session import get_session
from api.forum import instructors
from api.repo import catalog as repo
from api.schemas.catalog import (
    CatalogYearOut,
    CourseDetail,
    CourseSummary,
    InstructorDetail,
    InstructorSummary,
    ProgramDetail,
    ProgramSummary,
)
from api.schemas.common import NOT_IMPLEMENTED, Page

router = APIRouter(tags=["catalog"], responses=NOT_IMPLEMENTED)

SessionDep = Annotated[Session, Depends(get_session)]

# Route functions carry comments, not docstrings: FastAPI copies docstrings into the frozen
# OpenAPI document. Defaults: the latest catalog year that has courses; only `published`
# program versions unless `show_unpublished_programs` is set.


@contextmanager
def _not_found() -> Iterator[None]:
    try:
        yield
    except repo.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _program_statuses() -> tuple[str, ...]:
    return repo.ALL_STATUSES if get_settings().show_unpublished_programs else repo.PUBLISHED


@router.get("/catalog-years", response_model=list[CatalogYearOut])
def list_catalog_years(session: SessionDep) -> list[CatalogYearOut]:
    return repo.list_catalog_years(session)


@router.get("/terms", response_model=list[Term])
def list_terms(session: SessionDep, catalog_year: str | None = None) -> list[Term]:
    with _not_found():
        year = repo.resolve_catalog_year(session, catalog_year)
    return repo.list_terms(session, year) if year else []


@router.get("/courses", response_model=Page[CourseSummary])
def search_courses(
    session: SessionDep,
    q: str | None = None,
    subject: str | None = None,
    level: int | None = Query(default=None, description="10000, 20000, ..."),
    quarter: Quarter | None = None,
    core_tag: str | None = None,
    max_workload_hours: float | None = Query(default=None, ge=0),
    max_difficulty: float | None = Query(default=None, ge=0),
    catalog_year: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[CourseSummary]:
    if level is not None and (level % 10000 or not 10000 <= level <= 90000):
        raise HTTPException(422, "level must be one of 10000, 20000, ..., 90000")
    with _not_found():
        year = repo.resolve_catalog_year(session, catalog_year)
    items, total = repo.search_courses(
        session,
        year,
        q=q,
        subject=subject,
        level=level,
        quarter=quarter,
        core_tag=core_tag,
        max_workload_hours=max_workload_hours,
        max_difficulty=max_difficulty,
        limit=limit,
        offset=offset,
    )
    return Page[CourseSummary](items=items, total=total, limit=limit, offset=offset)


# `code` may be "CMSC 14100" (URL-encoded), "CMSC-14100" or "CMSC14100".
@router.get("/courses/{code}", response_model=CourseDetail)
def get_course(session: SessionDep, code: str, catalog_year: str | None = None) -> CourseDetail:
    with _not_found():
        year = repo.require_catalog_year(session, catalog_year)
        return repo.course_detail(session, year, code, statuses=_program_statuses())


@router.get("/course-lists/{name}", response_model=CourseList)
def get_course_list(session: SessionDep, name: str, catalog_year: str | None = None) -> CourseList:
    with _not_found():
        year = repo.require_catalog_year(session, catalog_year)
        return repo.course_list(session, year, name)


@router.get("/programs", response_model=list[ProgramSummary])
def list_programs(
    session: SessionDep, catalog_year: str | None = None, type: ProgramType | None = None
) -> list[ProgramSummary]:
    with _not_found():
        year = repo.resolve_catalog_year(session, catalog_year)
    return repo.list_programs(session, year, program_type=type, statuses=_program_statuses())


@router.get("/programs/{program_id}", response_model=ProgramDetail)
def get_program(
    session: SessionDep, program_id: str, catalog_year: str | None = None
) -> ProgramDetail:
    with _not_found():
        year = repo.require_catalog_year(session, catalog_year)
        return repo.program_detail(session, year, program_id, statuses=_program_statuses())


# Courses that can fill the node (a group or bounded_parts node: any child or part), by code.
@router.get("/programs/{program_id}/eligible", response_model=list[CourseSummary])
def eligible_courses(
    session: SessionDep,
    program_id: str,
    node: str = Query(description="node path, e.g. cmsc-bs/electives"),
    catalog_year: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CourseSummary]:
    with _not_found():
        year = repo.require_catalog_year(session, catalog_year)
        return repo.eligible_courses(
            session, year, program_id, node, limit=limit, statuses=_program_statuses()
        )


# Instructor names are public (P03-12); ratings stay behind login.
@router.get("/instructors", response_model=Page[InstructorSummary])
def list_instructors(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[InstructorSummary]:
    items, total = instructors.search(session, q, limit=limit, offset=offset)
    return Page[InstructorSummary](items=items, total=total, limit=limit, offset=offset)


# The courses an instructor teaches; per-course ratings only for logged-in readers.
@router.get("/instructors/{slug}", response_model=InstructorDetail)
def get_instructor(
    session: SessionDep,
    reader: Annotated[SessionData | None, Depends(optional_session)],
    slug: str,
) -> InstructorDetail:
    with _not_found():
        return instructors.detail(session, slug, with_ratings=reader is not None)
