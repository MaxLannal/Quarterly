import datetime as dt

from planner_core.models import (
    AttributeValue,
    CourseRelation,
    Expr,
    Node,
    OfferingPattern,
    PlanItem,
    Policy,
    ProgramType,
    Section,
    Source,
)
from pydantic import BaseModel


class CatalogYearOut(BaseModel):
    id: str
    published_at: dt.date | None = None


class CourseSummary(BaseModel):
    code: str
    title: str
    units: int
    core_tags: list[str] = []
    tags: list[str] = []
    crosslists: list[str] = []
    attributes: list[AttributeValue] = []


class InstructorSummary(BaseModel):
    slug: str
    display_name: str
    department: str | None = None


class CourseInstructorOut(BaseModel):
    page_id: int
    instructor: InstructorSummary
    first_term: str | None = None
    last_term: str | None = None
    n_terms: int = 0


class CountsToward(BaseModel):
    program_id: str
    program_name: str
    node_id: str
    label: str | None = None


class CourseDetail(CourseSummary):
    catalog_year: str
    description: str | None = None
    notes: str | None = None
    prereq: Expr | None = None
    coreq: Expr | None = None
    restrictions: Expr | None = None
    prereq_text: str | None = None
    #: Human form of `prereq`, e.g. "CMSC 14200 and (MATH 15900 or MATH 16300)".
    prereq_human: str | None = None
    #: Course codes this course's prerequisites name / courses whose prerequisites name it.
    needs: list[str] = []
    unlocks: list[str] = []
    relations: list[CourseRelation] = []
    offerings: list[OfferingPattern] = []
    sections: list[Section] = []
    instructors: list[CourseInstructorOut] = []
    counts_toward: list[CountsToward] = []
    source: Source | None = None


class ProgramSummary(BaseModel):
    id: str
    name: str
    type: ProgramType
    degree: str | None = None
    department: str | None = None
    parent_id: str | None = None
    catalog_year: str
    status: str
    verified_at: dt.date | None = None


class ProgramDetail(ProgramSummary):
    version_id: int
    rules: Node
    policy: Policy
    sources: list[Source] = []
    checksum: str
    verified_by: str | None = None
    sample_path: list[PlanItem] = []


class InstructorCourse(BaseModel):
    code: str
    title: str
    page_id: int
    n_terms: int = 0
    attributes: list[AttributeValue] = []


class InstructorDetail(InstructorSummary):
    courses: list[InstructorCourse] = []
