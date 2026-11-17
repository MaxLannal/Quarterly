"""Catalog reads behind the public catalog endpoints: catalog years, terms, course search and
detail, course lists, programs, and the courses that can fill a program node.

Conventions:
- The default catalog year is the latest catalog year that has courses.
- A catalog year "2026-27" owns the terms of its academic year: 2026-AU, 2027-WI, 2027-SP and
  2027-SU.
- Course-level attributes are `attribute_value` rows with `subject_type = 'course'` and
  `subject_id` = the course code ("CMSC 14100").
- Program versions are filtered by status by the caller (`statuses`): only `published` ones
  reach students unless `show_unpublished_programs` is set.

`SelectorMatcher` implements docs/CONTRACTS.md "Selector semantics" for `counts_toward` and
`eligible`. TODO: switch to planner_core's matcher once the verifier (prompt 02) provides one,
so the requirement rail and the trusted verifier can never disagree.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator, Sequence
from typing import get_args

import sqlalchemy as sa
from planner_core.dsl import expr_courses, expr_to_text, iter_nodes
from planner_core.models import (
    AttributeKey,
    AttributeValue,
    BoundedPartsNode,
    Catalog,
    Course,
    CourseList,
    CourseRelation,
    Expr,
    GroupNode,
    OfferingPattern,
    Part,
    ProgramRules,
    Section,
    SelectNode,
    Selector,
    SlotNode,
    Source,
    Term,
)
from planner_core.terms import QUARTERS, term_key
from sqlalchemy.orm import Session, aliased

from api.db import models as m
from api.schemas.catalog import (
    CatalogYearOut,
    CountsToward,
    CourseDetail,
    CourseSummary,
    ProgramDetail,
    ProgramSummary,
)

PUBLISHED: tuple[str, ...] = ("published",)
ALL_STATUSES: tuple[str, ...] = ("draft", "review", "published")
#: A quarter counts as offered (course search `quarter` filter) from this predicted probability.
OFFERED_MIN = 0.3
#: Minimum pg_trgm word similarity for a fuzzy match of one query word to a title
#: ("algoritms" -> "Algorithms"); pg_trgm's own default `word_similarity_threshold`.
FUZZY_MIN = 0.6
ATTRIBUTE_KEYS: frozenset[str] = frozenset(get_args(AttributeKey))

AnyNode = GroupNode | SlotNode | SelectNode | BoundedPartsNode
#: Leaves a course can be assigned to: slots, selects and bounded_parts parts.
FillTarget = SlotNode | SelectNode | Part

_CODE = re.compile(r"^\s*([A-Za-z]{2,5})[\s\-_+]*(\d{5})\s*$")


class NotFoundError(LookupError):
    """Unknown catalog year, course, list, program or node. The message is the 404 detail."""


# ------------------------------------------------------------------------- Selector matching


class SelectorMatcher:
    """Which courses a selector or a rule node accepts (docs/CONTRACTS.md "Selector semantics").

    A course matches a selector when no code of its cross-list group is excluded and at least
    one code of the group meets every criterion that is set (so a cross-listed code matches
    wherever its partner does). Criteria: `codes` (any), `subject`, `number_range` (inclusive),
    `tags` (any; a course's tags include `core:<t>` for each core tag), `list` (members of the
    named list and, recursively, its sublists) and `union` (any sub-selector)."""

    def __init__(self, catalog: Catalog) -> None:
        self._courses = {c.code: c for c in catalog.courses}
        self._groups: dict[str, frozenset[str]] = {}
        for group in catalog.crosslist_groups:
            members = frozenset(group)
            for code in group:
                self._groups[code] = self._groups.get(code, frozenset()) | members
        self._lists = {cl.name: cl for cl in catalog.course_lists}
        self._members: dict[str, frozenset[str]] = {}

    def group(self, code: str) -> frozenset[str]:
        """`code` and every code cross-listed with it."""
        return self._groups.get(code, frozenset({code}))

    def tags(self, code: str) -> frozenset[str]:
        course = self._courses.get(code)
        if course is None:
            return frozenset()
        return frozenset(course.tags) | {f"core:{t}" for t in course.core_tags}

    def list_members(self, name: str) -> frozenset[str]:
        """Courses of the named list plus those of its sublists (recursively). Unknown names
        and cycles contribute nothing."""
        if (cached := self._members.get(name)) is not None:
            return cached
        seen: set[str] = set()
        codes: set[str] = set()
        stack = [name]
        while stack:
            current = stack.pop()
            if current in seen or (course_list := self._lists.get(current)) is None:
                continue
            seen.add(current)
            codes.update(course_list.courses)
            stack.extend(course_list.sublists)
        self._members[name] = frozenset(codes)
        return self._members[name]

    def matches(self, code: str, selector: Selector) -> bool:
        group = self.group(code)
        if group & set(selector.exclude):
            return False
        return any(self._meets_criteria(member, selector) for member in sorted(group))

    def _meets_criteria(self, code: str, selector: Selector) -> bool:
        subject, number = code.split(" ")
        if selector.codes and code not in selector.codes:
            return False
        if selector.subject is not None and subject != selector.subject:
            return False
        if selector.number_range is not None:
            low, high = selector.number_range
            if not low <= int(number) <= high:
                return False
        if selector.tags and not self.tags(code) & set(selector.tags):
            return False
        if selector.list_ is not None and code not in self.list_members(selector.list_):
            return False
        return not selector.union or any(self.matches(code, sub) for sub in selector.union)

    def fills(self, code: str, node: AnyNode | Part) -> bool:
        """Whether `code` can fill `node`: a slot's alternatives, a select's or part's selector,
        any part of a bounded_parts node, or any child of a group."""
        if isinstance(node, SlotNode):
            return bool(self.group(code) & set(node.any_of))
        if isinstance(node, SelectNode | Part):
            return self.matches(code, node.from_)
        if isinstance(node, BoundedPartsNode):
            return any(self.matches(code, part.from_) for part in node.parts)
        return any(self.fills(code, child) for child in node.children)


def fill_targets(program: ProgramRules) -> Iterator[tuple[str, FillTarget]]:
    """Every slot, select and bounded_parts part with its path, in tree order."""
    for path, node in iter_nodes(program):
        if isinstance(node, SlotNode | SelectNode):
            yield path, node
        elif isinstance(node, BoundedPartsNode):
            for part in node.parts:
                yield f"{path}/{part.id}", part


def find_node(program: ProgramRules, path: str) -> AnyNode | Part:
    """The node or part at `path` (`cmsc-bs/electives`; the program prefix may be omitted)."""
    nodes: dict[str, AnyNode | Part] = dict(iter_nodes(program))
    for node_path, node in iter_nodes(program):
        if isinstance(node, BoundedPartsNode):
            nodes.update({f"{node_path}/{part.id}": part for part in node.parts})
    key = path.strip().strip("/")
    for candidate in (key, f"{program.id}/{key}"):
        if key and candidate in nodes:
            return nodes[candidate]
    raise NotFoundError(f"Unknown node {path!r} in program {program.id}")


# ---------------------------------------------------------------------------- Catalog years


def normalize_code(raw: str) -> str | None:
    """`CMSC 14100`, `cmsc-14100`, `CMSC14100` -> `CMSC 14100`; None if `raw` is not a code."""
    match = _CODE.match(raw)
    return f"{match[1].upper()} {match[2]}" if match else None


def latest_catalog_year(session: Session) -> str | None:
    """The latest catalog year that has courses (the default everywhere)."""
    return session.scalar(sa.select(sa.func.max(m.Course.catalog_year)))


def resolve_catalog_year(session: Session, catalog_year: str | None) -> str | None:
    """The requested catalog year (NotFoundError if unknown), else the default; None when no
    catalog year has courses yet."""
    if catalog_year is None:
        return latest_catalog_year(session)
    if session.get(m.CatalogYear, catalog_year) is None:
        raise NotFoundError(f"Unknown catalog year {catalog_year}")
    return catalog_year


def require_catalog_year(session: Session, catalog_year: str | None) -> str:
    year = resolve_catalog_year(session, catalog_year)
    if year is None:
        raise NotFoundError("No catalog data has been loaded yet")
    return year


def list_catalog_years(session: Session) -> list[CatalogYearOut]:
    rows = session.scalars(sa.select(m.CatalogYear).order_by(m.CatalogYear.id.desc()))
    return [CatalogYearOut(id=row.id, published_at=row.published_at) for row in rows]


def list_terms(session: Session, catalog_year: str) -> list[Term]:
    """The terms of the catalog year's academic year, in chronological order."""
    start = int(catalog_year[:4])
    rows = session.scalars(
        sa.select(m.Term).where(
            sa.or_(
                sa.and_(m.Term.year == start, m.Term.quarter == "AU"),
                sa.and_(m.Term.year == start + 1, m.Term.quarter != "AU"),
            )
        )
    )
    terms = [Term(id=row.id, start=row.start, end=row.end) for row in rows]
    return sorted(terms, key=lambda t: term_key(t.id))


# ---------------------------------------------------------------------------------- Courses


def _attribute(row: m.AttributeValue) -> AttributeValue:
    # A cold-start `estimate` is a planner_core `prior` (see AttributeValue.method).
    method = row.method if row.method in ("prior", "forum", "blend") else "prior"
    return AttributeValue.model_validate(
        {
            "subject_type": "course",
            "subject_id": row.subject_id,
            "key": row.key,
            "value": row.value,
            "ci_low": row.ci_low,
            "ci_high": row.ci_high,
            "n": row.n,
            "method": method,
        }
    )


def _course_attributes(session: Session, codes: Collection[str]) -> dict[str, list[AttributeValue]]:
    if not codes:
        return {}
    rows = session.scalars(
        sa.select(m.AttributeValue)
        .where(
            m.AttributeValue.subject_type == "course",
            m.AttributeValue.subject_id.in_(codes),
            m.AttributeValue.key.in_(ATTRIBUTE_KEYS),
        )
        .order_by(m.AttributeValue.key)
    )
    found: dict[str, list[AttributeValue]] = {}
    for row in rows:
        found.setdefault(row.subject_id, []).append(_attribute(row))
    return found


def _crosslists(session: Session, course_ids: Collection[int]) -> dict[int, list[str]]:
    """Course id -> the other codes of its cross-list group."""
    if not course_ids:
        return {}
    mine, other = aliased(m.CrosslistGroup), aliased(m.CrosslistGroup)
    rows = session.execute(
        sa.select(mine.course_id, m.Course.code)
        .select_from(mine)
        .join(other, sa.and_(other.group_id == mine.group_id, other.course_id != mine.course_id))
        .join(m.Course, m.Course.id == other.course_id)
        .where(mine.course_id.in_(course_ids))
        .distinct()
    )
    found: dict[int, set[str]] = {}
    for course_id, code in rows:
        found.setdefault(course_id, set()).add(code)
    return {course_id: sorted(codes) for course_id, codes in found.items()}


def _summaries(session: Session, rows: Sequence[m.Course]) -> list[CourseSummary]:
    crosslists = _crosslists(session, [row.id for row in rows])
    attributes = _course_attributes(session, [row.code for row in rows])
    return [
        CourseSummary(
            code=row.code,
            title=row.title,
            units=row.units,
            core_tags=list(row.core_tags),
            tags=list(row.tags),
            crosslists=crosslists.get(row.id, []),
            attributes=attributes.get(row.code, []),
        )
        for row in rows
    ]


def search_courses(
    session: Session,
    catalog_year: str | None,
    *,
    q: str | None = None,
    subject: str | None = None,
    level: int | None = None,
    quarter: str | None = None,
    core_tag: str | None = None,
    max_workload_hours: float | None = None,
    max_difficulty: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[CourseSummary], int]:
    """One page of matching courses and the total count.

    `q` matches the code ignoring spaces and dashes ("cmsc 141", "MATH20700"), the title as a
    substring, or word by word: every word must appear in the code or title or be pg_trgm
    word-similar to the title (typos). Results rank exact code, code prefix, code substring,
    title prefix, title substring, then word matches; within a rank by word similarity of
    the whole query to the title, then by code. `level` 20000 means numbers 20000-29999;
    `quarter` needs a predicted p_offered of at least OFFERED_MIN; the attribute bounds use
    course-level values and drop courses that have none."""
    if catalog_year is None:
        return [], 0
    course = m.Course
    where: list[sa.ColumnElement[bool]] = [course.catalog_year == catalog_year]
    order: list[sa.ColumnElement[object]] = []
    if subject:
        where.append(course.subject == subject.strip().upper())
    if level is not None:
        where.append(sa.cast(course.number, sa.Integer).between(level, level + 9999))
    if quarter is not None:
        offered = m.OfferingPattern
        where.append(
            sa.exists().where(
                offered.course_id == course.id,
                offered.quarter == quarter,
                offered.p_offered >= OFFERED_MIN,
            )
        )
    if core_tag and core_tag.strip():
        tag = core_tag.strip().removeprefix("core:")
        where.append(sa.literal(tag, sa.Text) == sa.any_(course.core_tags))
    for key, bound in (("workload_hours", max_workload_hours), ("difficulty", max_difficulty)):
        if bound is not None:
            attr = m.AttributeValue
            where.append(
                sa.exists().where(
                    attr.subject_type == "course",
                    attr.subject_id == course.code,
                    attr.key == key,
                    attr.value <= bound,
                )
            )
    text = " ".join((q or "").split())
    if text:
        compact = re.sub(r"[\s\-_+]", "", text).upper()
        code = sa.func.replace(course.code, " ", "", type_=sa.Text)
        code_hit = code.icontains(compact, autoescape=True)
        title_hit = course.title.icontains(text, autoescape=True)
        words_hit = sa.and_(
            *(
                sa.or_(
                    code.icontains(word, autoescape=True),
                    course.title.icontains(word, autoescape=True),
                    sa.func.word_similarity(sa.literal(word, sa.Text), course.title) >= FUZZY_MIN,
                )
                for word in text.split()
            )
        )
        where.append(sa.or_(code_hit, title_hit, words_hit))
        rank = sa.case(
            (code == compact, 0),
            (code.istartswith(compact, autoescape=True), 1),
            (code_hit, 2),
            (course.title.istartswith(text, autoescape=True), 3),
            (title_hit, 4),
            else_=5,
        )
        similarity = sa.func.word_similarity(sa.literal(text, sa.Text), course.title)
        order = [rank, similarity.desc()]
    total = session.scalar(sa.select(sa.func.count()).select_from(course).where(*where)) or 0
    rows = session.scalars(
        sa.select(course).where(*where).order_by(*order, course.code).limit(limit).offset(offset)
    ).all()
    return _summaries(session, rows), total


def _course_row(session: Session, catalog_year: str, raw_code: str) -> m.Course:
    code = normalize_code(raw_code)
    if code is None:
        raise NotFoundError(f"Unknown course {raw_code!r} (expected a code like 'CMSC 14100')")
    row = session.scalar(
        sa.select(m.Course).where(m.Course.catalog_year == catalog_year, m.Course.code == code)
    )
    if row is None:
        raise NotFoundError(f"Unknown course {code} in catalog year {catalog_year}")
    return row


def _expr(data: object) -> Expr | None:
    return None if data is None else Expr.model_validate(data)


def _unlocks(session: Session, catalog_year: str, codes: Collection[str]) -> list[str]:
    """Courses whose prerequisites name one of `codes` (a course and its cross-listings)."""
    as_text = sa.cast(m.Requisite.prereq, sa.Text)
    rows = session.execute(
        sa.select(m.Course.code, m.Requisite.prereq)
        .join(m.Course, m.Course.id == m.Requisite.course_id)
        .where(
            m.Requisite.catalog_year == catalog_year,
            sa.or_(*(as_text.contains(f'"{code}"', autoescape=True) for code in codes)),
        )
    )
    wanted = set(codes)
    found = set()
    for code, prereq in rows:
        expr = _expr(prereq)
        if code not in wanted and expr is not None and expr_courses(expr) & wanted:
            found.add(code)
    return sorted(found)


def _relations(session: Session, course_id: int) -> list[CourseRelation]:
    a, b, rel = aliased(m.Course), aliased(m.Course), m.CourseRelation
    rows = session.execute(
        sa.select(a.code, b.code, rel.kind, rel.source)
        .select_from(rel)
        .join(a, a.id == rel.course_a)
        .join(b, b.id == rel.course_b)
        .where(sa.or_(rel.course_a == course_id, rel.course_b == course_id))
        .order_by(rel.kind, a.code, b.code)
    )
    return [
        CourseRelation.model_validate({"a": code_a, "b": code_b, "kind": kind, "source": source})
        for code_a, code_b, kind, source in rows
    ]


def _offerings(session: Session, course: m.Course) -> list[OfferingPattern]:
    rows = session.scalars(
        sa.select(m.OfferingPattern).where(m.OfferingPattern.course_id == course.id)
    )
    patterns = [
        OfferingPattern.model_validate(
            {
                "course": course.code,
                "quarter": row.quarter,
                "p_offered": row.p_offered,
                "evidence_terms": list(row.evidence_terms),
                "method": row.method,
            }
        )
        for row in rows
    ]
    return sorted(patterns, key=lambda p: QUARTERS.index(p.quarter))


def _sections(session: Session, course: m.Course) -> list[Section]:
    rows = session.scalars(sa.select(m.Section).where(m.Section.course_id == course.id))
    sections = [
        Section.model_validate(
            {
                "term": row.term_id,
                "course": course.code,
                "section_no": row.section_no,
                "component": row.component,
                "instructor_ids": [str(i) for i in row.instructor_ids],
                "meetings": row.meetings or [],
                "status": row.status,
            }
        )
        for row in rows
    ]
    return sorted(sections, key=lambda s: (term_key(s.term), s.section_no))


def course_detail(
    session: Session, catalog_year: str, raw_code: str, *, statuses: Sequence[str] = PUBLISHED
) -> CourseDetail:
    """Everything the course page shows. `statuses`: program versions for `counts_toward`."""
    from api.forum.pages import course_instructors  # the forum imports this module

    row = _course_row(session, catalog_year, raw_code)
    summary = _summaries(session, [row])[0]
    requisite = session.scalar(
        sa.select(m.Requisite).where(
            m.Requisite.course_id == row.id, m.Requisite.catalog_year == catalog_year
        )
    )
    prereq = _expr(requisite.prereq) if requisite else None
    return CourseDetail(
        **dict(summary),
        catalog_year=catalog_year,
        description=row.description,
        notes=row.notes,
        prereq=prereq,
        coreq=_expr(requisite.coreq) if requisite else None,
        restrictions=_expr(requisite.restrictions) if requisite else None,
        prereq_text=requisite.raw_text if requisite else None,
        prereq_human=expr_to_text(prereq) if prereq else None,
        needs=sorted(expr_courses(prereq)) if prereq else [],
        unlocks=_unlocks(session, catalog_year, [row.code, *summary.crosslists]),
        relations=_relations(session, row.id),
        offerings=_offerings(session, row),
        sections=_sections(session, row),
        # One forum page per course x instructor (names are public, P03-12).
        instructors=course_instructors(session, row.code),
        counts_toward=counts_toward(session, catalog_year, row.code, statuses=statuses),
        source=Source.model_validate(row.source) if row.source else None,
    )


# ----------------------------------------------------------------------------- Course lists


def _codes_by_id(session: Session, ids: Collection[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = session.execute(sa.select(m.Course.id, m.Course.code).where(m.Course.id.in_(ids)))
    return {course_id: code for course_id, code in rows}


def _course_list(row: m.CourseList, codes: dict[int, str]) -> CourseList:
    return CourseList.model_validate(
        {
            "name": row.name,
            "label": row.label,
            "courses": [codes[i] for i in row.course_ids if i in codes],
            "sublists": list(row.sublists),
            "source": row.source,
            "needs_review": row.needs_review,
        }
    )


def course_list(session: Session, catalog_year: str, name: str) -> CourseList:
    row = session.scalar(
        sa.select(m.CourseList).where(
            m.CourseList.catalog_year == catalog_year, m.CourseList.name == name
        )
    )
    if row is None:
        raise NotFoundError(f"Unknown course list {name} in catalog year {catalog_year}")
    return _course_list(row, _codes_by_id(session, row.course_ids))


def load_catalog(session: Session, catalog_year: str) -> Catalog:
    """The catalog facts selector matching reads: courses, cross-list groups, course lists."""
    rows = session.execute(
        sa.select(
            m.Course.id,
            m.Course.code,
            m.Course.title,
            m.Course.units,
            m.Course.core_tags,
            m.Course.tags,
        ).where(m.Course.catalog_year == catalog_year)
    ).all()
    codes = {row.id: row.code for row in rows}
    groups: dict[str, list[str]] = {}
    for group_id, code in session.execute(
        sa.select(m.CrosslistGroup.group_id, m.Course.code)
        .join(m.Course, m.Course.id == m.CrosslistGroup.course_id)
        .where(m.Course.catalog_year == catalog_year)
    ):
        groups.setdefault(group_id, []).append(code)
    lists = session.scalars(
        sa.select(m.CourseList).where(m.CourseList.catalog_year == catalog_year)
    )
    return Catalog.model_construct(
        catalog_year=catalog_year,
        # Read back from validated seed rows, so construct without re-validating.
        courses=[
            Course.model_construct(
                code=row.code,
                title=row.title,
                units=row.units,
                core_tags=list(row.core_tags),
                tags=list(row.tags),
            )
            for row in rows
        ],
        crosslist_groups=[sorted(g) for g in groups.values() if len(g) > 1],
        course_lists=[_course_list(cl, codes) for cl in lists],
    )


# --------------------------------------------------------------------------------- Programs


def _program_rows(
    session: Session,
    catalog_year: str,
    statuses: Sequence[str],
    *,
    program_id: str | None = None,
    program_type: str | None = None,
) -> list[tuple[m.Program, m.ProgramVersion]]:
    stmt = (
        sa.select(m.Program, m.ProgramVersion)
        .join(m.ProgramVersion, m.ProgramVersion.program_id == m.Program.id)
        .where(
            m.ProgramVersion.catalog_year == catalog_year,
            m.ProgramVersion.status.in_(statuses),
        )
        .order_by(m.Program.name, m.Program.id)
    )
    if program_id is not None:
        stmt = stmt.where(m.Program.id == program_id)
    if program_type is not None:
        stmt = stmt.where(m.Program.type == program_type)
    return [(program, version) for program, version in session.execute(stmt)]


def _program_summary(program: m.Program, version: m.ProgramVersion) -> ProgramSummary:
    return ProgramSummary.model_validate(
        {
            "id": program.id,
            "name": program.name,
            "type": program.type,
            "degree": program.degree,
            "department": program.department,
            "parent_id": program.parent_id,
            "catalog_year": version.catalog_year,
            "status": version.status,
            "verified_at": version.verified_at,
        }
    )


def list_programs(
    session: Session,
    catalog_year: str | None,
    *,
    program_type: str | None = None,
    statuses: Sequence[str] = PUBLISHED,
) -> list[ProgramSummary]:
    if catalog_year is None:
        return []
    rows = _program_rows(session, catalog_year, statuses, program_type=program_type)
    return [_program_summary(program, version) for program, version in rows]


def _one_program(
    session: Session, catalog_year: str, program_id: str, statuses: Sequence[str]
) -> tuple[m.Program, m.ProgramVersion]:
    rows = _program_rows(session, catalog_year, statuses, program_id=program_id)
    if rows:
        return rows[0]
    if session.get(m.Program, program_id) is None:
        raise NotFoundError(f"Unknown program {program_id}")
    which = "published version" if tuple(statuses) == PUBLISHED else "version"
    raise NotFoundError(f"Program {program_id} has no {which} for catalog year {catalog_year}")


def program_detail(
    session: Session, catalog_year: str, program_id: str, *, statuses: Sequence[str] = PUBLISHED
) -> ProgramDetail:
    program, version = _one_program(session, catalog_year, program_id, statuses)
    rules = ProgramRules.model_validate(version.rules)
    return ProgramDetail(
        **dict(_program_summary(program, version)),
        version_id=version.id,
        rules=rules.rules,
        policy=rules.policy,
        sources=[Source.model_validate(s) for s in version.sources],
        checksum=version.checksum,
        verified_by=version.verified_by,
    )


def counts_toward(
    session: Session, catalog_year: str, code: str, *, statuses: Sequence[str] = PUBLISHED
) -> list[CountsToward]:
    """Program requirements (slots, selects, parts) that `code` can fill."""
    programs = _program_rows(session, catalog_year, statuses)
    if not programs:
        return []
    matcher = SelectorMatcher(load_catalog(session, catalog_year))
    found: list[CountsToward] = []
    for program, version in programs:
        rules = ProgramRules.model_validate(version.rules)
        found += [
            CountsToward(
                program_id=program.id, program_name=program.name, node_id=path, label=node.label
            )
            for path, node in fill_targets(rules)
            if matcher.fills(code, node)
        ]
    return found


def eligible_courses(
    session: Session,
    catalog_year: str,
    program_id: str,
    node: str,
    *,
    limit: int = 50,
    statuses: Sequence[str] = PUBLISHED,
) -> list[CourseSummary]:
    """Courses that can fill the node at `node` (a group or bounded_parts node: any of its
    children or parts), by code."""
    _, version = _one_program(session, catalog_year, program_id, statuses)
    target = find_node(ProgramRules.model_validate(version.rules), node)
    catalog = load_catalog(session, catalog_year)
    matcher = SelectorMatcher(catalog)
    codes = sorted(c.code for c in catalog.courses if matcher.fills(c.code, target))[:limit]
    if not codes:
        return []
    rows = session.scalars(
        sa.select(m.Course)
        .where(m.Course.catalog_year == catalog_year, m.Course.code.in_(codes))
        .order_by(m.Course.code)
    ).all()
    return _summaries(session, rows)
