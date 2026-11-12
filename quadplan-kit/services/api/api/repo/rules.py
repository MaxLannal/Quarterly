"""Postgres -> planner_core inputs for one plan: the `RuleSet` and the `Catalog` that
`planner_core.verify` reads.

Only what this plan can touch is loaded, so the cost does not grow with the catalog:
- rules: the program versions the plan lists, the College policy of the catalog year, and
  the requisites of the plan's courses;
- catalog facts: the plan's courses and their cross-listed partners, relations that involve
  them, every course list of the year (codes only), offering patterns, attribute values and
  the posted sections of the plan's courses in the plan's terms.

A term has a "posted schedule" when it has any section. To keep that fact when none of the
plan's courses is offered, one section of the term is loaded as a marker.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from planner_core.models import (
    AttributeValue,
    Catalog,
    CollegePolicy,
    Course,
    CourseList,
    CourseRelation,
    Meeting,
    OfferingPattern,
    PlanState,
    ProgramRules,
    Requisite,
    RuleSet,
    Section,
)
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from api.db import models as m

_ATTRIBUTE_METHODS = ("prior", "forum", "blend")


class UnknownProgramsError(Exception):
    """The plan lists programs that have no usable version for its catalog year."""

    def __init__(self, program_ids: list[str]) -> None:
        super().__init__(", ".join(program_ids))
        self.program_ids = program_ids


def load_programs(
    session: Session, plan: PlanState, *, show_unpublished: bool
) -> list[ProgramRules]:
    """The `program_version` of each listed program: the bound `version_id` when the plan has
    one, else the version of the plan's catalog year. Only `published` versions count unless
    `show_unpublished` is set. Raises `UnknownProgramsError` for anything else."""
    year = plan.catalog_year
    rows = session.execute(
        sa.select(m.ProgramVersion, m.Program.type)
        .join(m.Program, m.Program.id == m.ProgramVersion.program_id)
        .where(
            m.ProgramVersion.catalog_year == year,
            m.ProgramVersion.program_id.in_({p.program_id for p in plan.programs}),
        )
    ).all()
    by_program = {version.program_id: (version, kind) for version, kind in rows}
    programs: list[ProgramRules] = []
    unknown: list[str] = []
    for entry in plan.programs:
        version, kind = by_program.get(entry.program_id, (None, None))
        bound_elsewhere = entry.version_id is not None and (
            version is None or version.id != entry.version_id
        )
        hidden = version is not None and version.status != "published" and not show_unpublished
        if version is None or bound_elsewhere or hidden:
            unknown.append(entry.program_id)
            continue
        rules = ProgramRules.model_validate(version.rules)
        if rules.type is None:
            rules = rules.model_copy(update={"type": kind})
        if rules.id not in {p.id for p in programs}:
            programs.append(rules)
    if unknown:
        raise UnknownProgramsError(sorted(set(unknown)))
    return programs


def load_verify_inputs(
    session: Session, plan: PlanState, *, show_unpublished: bool = False
) -> tuple[RuleSet, Catalog]:
    year = plan.catalog_year
    programs = load_programs(session, plan, show_unpublished=show_unpublished)
    policy = session.get(m.CollegePolicy, year)
    college = CollegePolicy.model_validate(policy.rules) if policy is not None else None

    code_of: dict[int, str] = {
        course_id: code
        for course_id, code in session.execute(
            sa.select(m.Course.id, m.Course.code).where(m.Course.catalog_year == year)
        )
    }
    id_of = {code: course_id for course_id, code in code_of.items()}
    wanted = {i.course for i in plan.items if i.course} | {
        c.maps_to for c in plan.credits if c.maps_to
    }
    plan_ids = {id_of[code] for code in wanted if code in id_of}

    groups: dict[str, list[str]] = {}
    member_groups = sa.select(m.CrosslistGroup.group_id).where(
        m.CrosslistGroup.course_id.in_(plan_ids)
    )
    for group_id, course_id in session.execute(
        sa.select(m.CrosslistGroup.group_id, m.CrosslistGroup.course_id).where(
            m.CrosslistGroup.group_id.in_(member_groups)
        )
    ):
        if course_id in code_of:
            groups.setdefault(group_id, []).append(code_of[course_id])
    ids = plan_ids | {id_of[code] for group in groups.values() for code in group}
    codes = {code_of[i] for i in ids}

    relations = [
        CourseRelation(a=code_of[a], b=code_of[b], kind=kind)
        for a, b, kind in session.execute(
            sa.select(m.CourseRelation.course_a, m.CourseRelation.course_b, m.CourseRelation.kind)
            .where(sa.or_(m.CourseRelation.course_a.in_(ids), m.CourseRelation.course_b.in_(ids)))
            .order_by(m.CourseRelation.id)
        )
        if a in code_of and b in code_of
    ]
    courses = [
        Course(
            code=c.code,
            title=c.title,
            units=c.units,
            core_tags=c.core_tags,
            tags=c.tags,
            repeatable=c.repeatable,
        )
        for c in session.scalars(
            sa.select(m.Course).where(m.Course.id.in_(ids)).order_by(m.Course.code)
        )
    ]
    requisites = [
        Requisite.model_validate(
            {
                "course": code_of[r.course_id],
                "prereq": r.prereq,
                "coreq": r.coreq,
                "restrictions": r.restrictions,
                "raw_text": r.raw_text,
                "needs_review": r.needs_review,
            }
        )
        for r in session.scalars(
            sa.select(m.Requisite)
            .where(m.Requisite.catalog_year == year, m.Requisite.course_id.in_(ids))
            .order_by(m.Requisite.course_id)
        )
    ]
    course_lists = [
        CourseList(
            name=cl.name,
            label=cl.label,
            courses=[code_of[i] for i in cl.course_ids if i in code_of],
            sublists=cl.sublists,
        )
        for cl in session.scalars(
            sa.select(m.CourseList)
            .where(m.CourseList.catalog_year == year)
            .order_by(m.CourseList.name)
        )
    ]
    offerings = _valid(
        OfferingPattern,
        [
            {
                "course": code_of[o.course_id],
                "quarter": o.quarter,
                "p_offered": o.p_offered,
                "evidence_terms": o.evidence_terms,
                "method": o.method,
            }
            for o in session.scalars(
                sa.select(m.OfferingPattern)
                .where(m.OfferingPattern.course_id.in_(ids))
                .order_by(m.OfferingPattern.course_id, m.OfferingPattern.quarter)
            )
        ],
    )
    attributes = _valid(
        AttributeValue,
        [
            {
                "subject_id": a.subject_id,
                "key": a.key,
                "value": a.value,
                "ci_low": a.ci_low,
                "ci_high": a.ci_high,
                "n": a.n,
                "method": a.method if a.method in _ATTRIBUTE_METHODS else "prior",
            }
            for a in session.scalars(
                sa.select(m.AttributeValue)
                .where(
                    m.AttributeValue.subject_type == "course",
                    m.AttributeValue.subject_id.in_(codes),
                )
                .order_by(m.AttributeValue.subject_id, m.AttributeValue.key)
            )
        ],
    )
    catalog = Catalog(
        catalog_year=year,
        courses=courses,
        crosslist_groups=sorted(sorted(group) for group in groups.values() if len(group) > 1),
        relations=relations,
        course_lists=course_lists,
        offerings=offerings,
        sections=_sections(session, sorted({i.term for i in plan.items}), codes),
        attributes=attributes,
    )
    rules = RuleSet(catalog_year=year, programs=programs, college=college, requisites=requisites)
    return rules, catalog


def _valid[T: BaseModel](model: type[T], rows: list[dict[str, Any]]) -> list[T]:
    """Rows that fit the planner_core model. A row the verifier cannot read (an attribute key
    or quarter it does not know) is left out instead of failing the whole request."""
    found: list[T] = []
    for row in rows:
        try:
            found.append(model.model_validate(row))
        except ValidationError:
            continue
    return found


def _sections(session: Session, terms: list[str], codes: set[str]) -> list[Section]:
    """Sections of the plan's courses in the plan's terms, plus one marker section for each
    posted term in which none of them is offered."""

    def to_model(section: m.Section, code: str) -> Section:
        return Section(
            term=section.term_id,
            course=code,
            section_no=section.section_no,
            component=section.component,
            instructor_ids=[str(i) for i in section.instructor_ids],
            meetings=_valid(Meeting, section.meetings or []),
            status=section.status,
        )

    base = sa.select(m.Section, m.Course.code).join(m.Course, m.Course.id == m.Section.course_id)
    found = [
        to_model(section, code)
        for section, code in session.execute(
            base.where(m.Section.term_id.in_(terms), m.Course.code.in_(codes)).order_by(
                m.Section.id
            )
        )
    ]
    covered = {s.term for s in found}
    for term in terms:
        if term not in covered:
            marker = session.execute(
                base.where(m.Section.term_id == term).order_by(m.Section.id).limit(1)
            ).first()
            if marker is not None:
                found.append(to_model(marker[0], marker[1]))
    return found
