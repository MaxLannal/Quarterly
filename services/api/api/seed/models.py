"""Seed-file formats under `data/seed/<catalog_year>/` and golden plans under `data/golden/`.

Layout of one catalog year (all files optional; see docs/CONTRACTS.md):
    terms.yaml            {terms: [Term]}
    courses.yaml          {courses: [SeedCourse]}   and/or courses/*.yaml with the same shape
    summer_courses.yaml   SummerFile (Summer Session offerings; adds Summer to `terms_offered`)
    course_lists.yaml     {course_lists: [CourseList]}
    college_policy.yaml   CollegePolicy
    programs/*.yaml       one ProgramSeed per file
"""

from __future__ import annotations

import datetime as dt
from typing import Literal, Self

from planner_core.models import (
    CollegePolicy,
    CourseCode,
    CourseList,
    Degree,
    Expr,
    IssueCode,
    Model,
    PlanState,
    ProgramRules,
    ProgramType,
    Quarter,
    Slug,
    Source,
    Term,
)
from pydantic import Field, model_validator


class SeedCourse(Model):
    """One CourseLeaf course block, copied by hand."""

    code: CourseCode
    title: str
    units: int = Field(default=100, ge=0)
    description: str | None = None
    notes: str | None = None
    core_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    repeatable: bool = False
    crosslists: list[CourseCode] = Field(default_factory=list)
    equivalents: list[CourseCode] = Field(default_factory=list)
    mutually_exclusive: list[CourseCode] = Field(default_factory=list)
    replaces: list[CourseCode] = Field(default_factory=list)
    prereq: Expr | None = None
    coreq: Expr | None = None
    restrictions: Expr | None = None
    #: The catalog's prerequisite sentence, verbatim (stored as requisite.raw_text).
    prereq_text: str | None = None
    #: The catalog's "Terms Offered" line, if any.
    terms_offered: list[Quarter] = Field(default_factory=list)
    source: Source
    needs_review: bool = False


class CoursesFile(Model):
    courses: list[SeedCourse]


class SummerOffering(Model):
    """One Summer Session course open to College students, from the Summer Session course
    finder (summer.uchicago.edu; Richard, FEEDBACK "Check Summer Catalog", 2026-11-16).
    `source.quote` is the course code exactly as the course's page shows it."""

    code: CourseCode
    section: str | None = None
    title: str
    #: "Undergraduate", or "Both" (open to College and pre-college students).
    audience: Literal["Undergraduate", "Both"]
    session: str | None = None
    start: dt.date | None = None
    end: dt.date | None = None
    modality: str | None = None
    core: bool = False
    crosslists: list[CourseCode] = Field(default_factory=list)
    #: The course is in this catalog year's course list. Courses that are not are documented
    #: here but not added to the planner: the site states no units (OPEN_QUESTIONS DF-S1).
    in_catalog: bool
    source: Source


class SummerFile(Model):
    summer: int
    fetched: dt.date
    summer_courses: list[SummerOffering]


class TermsFile(Model):
    terms: list[Term]


class CourseListsFile(Model):
    course_lists: list[CourseList]


class ProgramSeed(ProgramRules):
    """A program version as authored: ProgramRules plus catalog metadata and sources."""

    name: str
    type: ProgramType
    degree: Degree | None = None
    department: str | None = None
    parent_id: Slug | None = None
    status: Literal["draft", "review", "published"] = "review"
    verified_by: str | None = None
    verified_at: dt.date | None = None
    sources: list[Source] = Field(min_length=1)

    def rules_only(self) -> ProgramRules:
        return ProgramRules(
            id=self.id,
            catalog_year=self.catalog_year,
            type=self.type,
            rules=self.rules,
            policy=self.policy,
        )


class GoldenPlan(Model):
    """A hand-written plan with a known verdict. `expect: fail` names the issue codes expected
    (each must appear in the report); `expect: pass` means no errors and an accepted
    certificate. The runner adds the College policy; the Core is checked only when the plan
    lists the core program. `checks` restricts which V-codes run (None = all)."""

    id: str
    description: str
    program: Slug
    expect: Literal["pass", "fail"]
    expected_codes: list[IssueCode] = Field(default_factory=list)
    checks: list[IssueCode] | None = None
    plan: PlanState

    @model_validator(mode="after")
    def _codes(self) -> Self:
        if self.expect == "fail" and not self.expected_codes:
            raise ValueError("must-fail golden plans name their expected issue codes")
        if self.expect == "pass" and self.expected_codes:
            raise ValueError("must-pass golden plans list no expected codes")
        if self.program not in {p.program_id for p in self.plan.programs}:
            raise ValueError(f"plan.programs must include {self.program}")
        return self


__all__ = [
    "CollegePolicy",
    "CourseListsFile",
    "CoursesFile",
    "GoldenPlan",
    "ProgramSeed",
    "SeedCourse",
    "TermsFile",
]
