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
    session: Session,
    plan: PlanState,
    *,
    show_unpublished: bool = False,
    whole_catalog: bool = False,
    section_terms: list[str] | None = None,
) -> tuple[RuleSet, Catalog]:
    """`whole_catalog` loads every course of the year instead of only the plan's (the plan
    generator chooses from all of them); `section_terms` adds posted sections of those terms.
    With RULES_CACHE_TTL_S > 0 the rows come from the in-process year cache (below)."""
    from api.config import get_settings

    ttl = get_settings().rules_cache_ttl_s
    if ttl > 0:
        return load_verify_inputs_cached(
            session,
            plan,
            ttl=ttl,
            show_unpublished=show_unpublished,
            whole_catalog=whole_catalog,
            section_terms=section_terms,
        )
    return _load_queried(
        session,
        plan,
        show_unpublished=show_unpublished,
        whole_catalog=whole_catalog,
        section_terms=section_terms,
    )


def _load_queried(
    session: Session,
    plan: PlanState,
    *,
    show_unpublished: bool,
    whole_catalog: bool,
    section_terms: list[str] | None,
) -> tuple[RuleSet, Catalog]:
    """`load_verify_inputs` straight from the database (only the plan's rows)."""
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
    if whole_catalog:
        plan_ids = set(code_of)

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
        sections=_sections(
            session, sorted({i.term for i in plan.items} | set(section_terms or [])), codes
        ),
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


# ------------------------------------------------------------------ in-process year cache
#
# Loading a plan's inputs costs about 20 queries; under load that round-trip time, not the
# verifier (a few ms), set the latency (prompt 12 load test). With RULES_CACHE_TTL_S > 0 each
# API process keeps one catalog year's rows in memory for that many seconds and builds every
# plan's RuleSet and Catalog from them, exactly as the queries above would (tested for
# equality). Data written meanwhile (a publish, the nightly attributes, a schedule run) shows
# up within the TTL. Off (0) by default; the Docker API turns it on.

import threading  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402


@dataclass
class _Year:
    loaded_at: float
    code_of: dict[int, str]
    courses: dict[int, Course]
    group_rows: list[tuple[str, int]]
    relations: list[tuple[int, int, str]]
    requisites: dict[int, list[Requisite]]
    course_lists: list[CourseList]
    offerings: dict[int, list[OfferingPattern]]
    attributes: dict[str, list[AttributeValue]]
    sections: list[tuple[int, str, Section]] = field(default_factory=list)  # (id, code, row)
    markers: dict[str, Section] = field(default_factory=dict)  # term -> its first section
    college: CollegePolicy | None = None


_years: dict[tuple[str, str], _Year] = {}
_lock = threading.Lock()


def clear_rules_cache() -> None:
    from api.repo.catalog import clear_catalog_cache  # the course pages' copy of the catalog

    with _lock:
        _years.clear()
    clear_catalog_cache()


def _load_year(session: Session, year: str) -> _Year:
    code_of = {
        i: c
        for i, c in session.execute(
            sa.select(m.Course.id, m.Course.code).where(m.Course.catalog_year == year)
        )
    }
    courses = {
        c.id: Course(
            code=c.code,
            title=c.title,
            units=c.units,
            core_tags=c.core_tags,
            tags=c.tags,
            repeatable=c.repeatable,
        )
        for c in session.scalars(sa.select(m.Course).where(m.Course.catalog_year == year))
    }
    group_rows = [
        (g, c)
        for g, c in session.execute(
            sa.select(m.CrosslistGroup.group_id, m.CrosslistGroup.course_id).where(
                m.CrosslistGroup.course_id.in_(list(code_of))
            )
        )
    ]
    relations = [
        (a, b, kind)
        for a, b, kind in session.execute(
            sa.select(m.CourseRelation.course_a, m.CourseRelation.course_b, m.CourseRelation.kind)
            .where(
                sa.or_(
                    m.CourseRelation.course_a.in_(list(code_of)),
                    m.CourseRelation.course_b.in_(list(code_of)),
                )
            )
            .order_by(m.CourseRelation.id)
        )
    ]
    requisites: dict[int, list[Requisite]] = {}
    for r in session.scalars(
        sa.select(m.Requisite)
        .where(m.Requisite.catalog_year == year)
        .order_by(m.Requisite.course_id)
    ):
        if r.course_id in code_of:
            requisites.setdefault(r.course_id, []).append(
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
            )
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
    offerings: dict[int, list[OfferingPattern]] = {}
    for o in session.scalars(
        sa.select(m.OfferingPattern)
        .where(m.OfferingPattern.course_id.in_(list(code_of)))
        .order_by(m.OfferingPattern.course_id, m.OfferingPattern.quarter)
    ):
        offerings.setdefault(o.course_id, []).extend(
            _valid(
                OfferingPattern,
                [
                    {
                        "course": code_of[o.course_id],
                        "quarter": o.quarter,
                        "p_offered": o.p_offered,
                        "evidence_terms": o.evidence_terms,
                        "method": o.method,
                    }
                ],
            )
        )
    attributes: dict[str, list[AttributeValue]] = {}
    codes = set(code_of.values())
    for a in session.scalars(
        sa.select(m.AttributeValue)
        .where(m.AttributeValue.subject_type == "course")
        .order_by(m.AttributeValue.subject_id, m.AttributeValue.key)
    ):
        if a.subject_id in codes:
            attributes.setdefault(a.subject_id, []).extend(
                _valid(
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
                    ],
                )
            )
    year_codes = set(code_of.values())
    markers: dict[str, Section] = {}
    for s, code in session.execute(
        sa.select(m.Section, m.Course.code)
        .join(m.Course, m.Course.id == m.Section.course_id)
        .where(
            m.Section.id.in_(
                sa.select(sa.func.min(m.Section.id)).group_by(m.Section.term_id).scalar_subquery()
            )
        )
    ):
        markers[s.term_id] = Section(
            term=s.term_id,
            course=code,
            section_no=s.section_no,
            component=s.component,
            instructor_ids=[str(i) for i in s.instructor_ids],
            meetings=_valid(Meeting, s.meetings or []),
            status=s.status,
        )
    sections = [
        (
            s.id,
            code,
            Section(
                term=s.term_id,
                course=code,
                section_no=s.section_no,
                component=s.component,
                instructor_ids=[str(i) for i in s.instructor_ids],
                meetings=_valid(Meeting, s.meetings or []),
                status=s.status,
            ),
        )
        for s, code in session.execute(
            sa.select(m.Section, m.Course.code)
            .join(m.Course, m.Course.id == m.Section.course_id)
            .where(m.Course.code.in_(year_codes))
            .order_by(m.Section.id)
        )
    ]
    policy = session.get(m.CollegePolicy, year)
    return _Year(
        loaded_at=time.monotonic(),
        code_of=code_of,
        courses=courses,
        group_rows=group_rows,
        relations=relations,
        requisites=requisites,
        course_lists=course_lists,
        offerings=offerings,
        attributes=attributes,
        sections=sections,
        markers=markers,
        college=CollegePolicy.model_validate(policy.rules) if policy is not None else None,
    )


_refreshing: set[tuple[str, str]] = set()


def _refresh(key: tuple[str, str], bind: Any, year: str) -> None:
    """Reload one year in the background; requests keep the old copy meanwhile."""
    try:
        with Session(bind) as fresh:
            loaded = _load_year(fresh, year)
        with _lock:
            _years[key] = loaded
    finally:
        with _lock:
            _refreshing.discard(key)


def _year(session: Session, year: str, ttl: float) -> _Year | None:
    """The cached copy of `year`, or None when it is not a catalog year (never loaded in full
    or cached, so a request naming a made-up year cannot make the server read whole tables)."""
    bind = session.get_bind()
    key = (str(getattr(bind, "url", "")), year)
    with _lock:
        found = _years.get(key)
        stale = found is not None and time.monotonic() - found.loaded_at >= ttl
        start = stale and key not in _refreshing
        if start:
            _refreshing.add(key)
    if found is not None:
        if start:  # stale: serve this copy, refresh once in the background
            threading.Thread(target=_refresh, args=(key, bind, year), daemon=True).start()
        return found
    if session.get(m.CatalogYear, year) is None:
        return None
    loaded = _load_year(session, year)
    with _lock:
        _years[key] = loaded
    return loaded


def preload_rules_cache(session: Session) -> int:
    """Load every catalog year into this process's cache (API start-up), so the first
    requests do not each pay for it. Returns the number of years loaded."""
    years = list(session.scalars(sa.select(m.CatalogYear.id)))
    for year in years:
        _year(session, year, ttl=float("inf"))
    return len(years)


def load_verify_inputs_cached(
    session: Session,
    plan: PlanState,
    *,
    ttl: float,
    show_unpublished: bool = False,
    whole_catalog: bool = False,
    section_terms: list[str] | None = None,
) -> tuple[RuleSet, Catalog]:
    """`load_verify_inputs` from the in-process year cache (programs are still read live)."""
    year = plan.catalog_year
    y = _year(session, year, ttl)
    if y is None:  # not a catalog year: the per-plan queries read only the plan's courses
        return _load_queried(
            session,
            plan,
            show_unpublished=show_unpublished,
            whole_catalog=whole_catalog,
            section_terms=section_terms,
        )
    programs = load_programs(session, plan, show_unpublished=show_unpublished)
    code_of = y.code_of
    id_of = {code: i for i, code in code_of.items()}
    wanted = {i.course for i in plan.items if i.course} | {
        c.maps_to for c in plan.credits if c.maps_to
    }
    plan_ids = set(code_of) if whole_catalog else {id_of[c] for c in wanted if c in id_of}
    member = {g for g, c in y.group_rows if c in plan_ids}
    groups: dict[str, list[str]] = {}
    for g, c in y.group_rows:
        if g in member and c in code_of:
            groups.setdefault(g, []).append(code_of[c])
    ids = plan_ids | {id_of[code] for group in groups.values() for code in group}
    codes = {code_of[i] for i in ids}
    relations = [
        CourseRelation(a=code_of[a], b=code_of[b], kind=kind)
        for a, b, kind in y.relations
        if (a in ids or b in ids) and a in code_of and b in code_of
    ]
    courses = sorted((y.courses[i] for i in ids if i in y.courses), key=lambda c: c.code)
    requisites = [r for i in sorted(ids) for r in y.requisites.get(i, [])]
    offerings = [o for i in sorted(ids) for o in y.offerings.get(i, [])]
    attributes = [a for code in sorted(codes) for a in y.attributes.get(code, [])]
    terms = sorted({i.term for i in plan.items} | set(section_terms or []))
    found = [s for _, code, s in y.sections if s.term in terms and code in codes]
    covered = {s.term for s in found}
    for term in terms:
        if term not in covered:
            marker = y.markers.get(term)
            if marker is not None:
                found.append(marker)
    catalog = Catalog(
        catalog_year=year,
        courses=courses,
        crosslist_groups=sorted(sorted(group) for group in groups.values() if len(group) > 1),
        relations=relations,
        course_lists=y.course_lists,
        offerings=offerings,
        sections=found,
        attributes=attributes,
    )
    rules = RuleSet(catalog_year=year, programs=programs, college=y.college, requisites=requisites)
    return rules, catalog
