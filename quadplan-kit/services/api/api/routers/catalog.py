from fastapi import APIRouter, Query
from planner_core.models import CourseList, ProgramType, Quarter, Term

from api.schemas.catalog import (
    CatalogYearOut,
    CourseDetail,
    CourseSummary,
    InstructorDetail,
    InstructorSummary,
    ProgramDetail,
    ProgramSummary,
)
from api.schemas.common import NOT_IMPLEMENTED, Page, not_implemented

router = APIRouter(tags=["catalog"], responses=NOT_IMPLEMENTED)


@router.get("/catalog-years", response_model=list[CatalogYearOut])
def list_catalog_years() -> list[CatalogYearOut]:
    raise not_implemented("M1 integration")


@router.get("/terms", response_model=list[Term])
def list_terms(catalog_year: str | None = None) -> list[Term]:
    raise not_implemented("M1 integration")


@router.get("/courses", response_model=Page[CourseSummary])
def search_courses(
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
    raise not_implemented("M1 integration")


@router.get("/courses/{code}", response_model=CourseDetail)
def get_course(code: str, catalog_year: str | None = None) -> CourseDetail:
    raise not_implemented("M1 integration")


@router.get("/course-lists/{name}", response_model=CourseList)
def get_course_list(name: str, catalog_year: str | None = None) -> CourseList:
    raise not_implemented("M1 integration")


@router.get("/programs", response_model=list[ProgramSummary])
def list_programs(
    catalog_year: str | None = None, type: ProgramType | None = None
) -> list[ProgramSummary]:
    raise not_implemented("M1 integration")


@router.get("/programs/{program_id}", response_model=ProgramDetail)
def get_program(program_id: str, catalog_year: str | None = None) -> ProgramDetail:
    raise not_implemented("M1 integration")


@router.get("/programs/{program_id}/eligible", response_model=list[CourseSummary])
def eligible_courses(
    program_id: str,
    node: str = Query(description="node path, e.g. cmsc-bs/electives"),
    catalog_year: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CourseSummary]:
    raise not_implemented("M1 integration")


@router.get("/instructors", response_model=Page[InstructorSummary])
def list_instructors(
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[InstructorSummary]:
    raise not_implemented("08")


@router.get("/instructors/{slug}", response_model=InstructorDetail)
def get_instructor(slug: str) -> InstructorDetail:
    raise not_implemented("08")
