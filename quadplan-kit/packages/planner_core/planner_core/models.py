"""Frozen contracts for planner_core (prompt 01). Pydantic v2 in, Pydantic v2 out; no I/O.

Sections follow docs/SPEC.md: "Requirements DSL" (Atom, Expr, the four node kinds, Selector,
Constraints, Policy, Source), "Data model" (catalog facts the verifier reads), and
"Verification engine" (PlanState, Goal, RuleSet, Report, Issue, Certificate, ChangeSet).

YAML authoring shorthands from the spec are accepted on input and normalised to one canonical
form on output, so `model_validate(model_dump())` is stable. See docs/CONTRACTS.md.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

# --------------------------------------------------------------------------------------------
# Scalars
# --------------------------------------------------------------------------------------------

COURSE_CODE_PATTERN = r"^[A-Z]{2,5} \d{5}$"
TERM_ID_PATTERN = r"^\d{4}-(AU|WI|SP|SU)$"
REL_TERM_PATTERN = r"^Y[1-6]-(AU|WI|SP|SU)$"
TERM_REF_PATTERN = r"^(\d{4}|Y[1-6])-(AU|WI|SP|SU)$"
CATALOG_YEAR_PATTERN = r"^\d{4}-\d{2}$"
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
NODE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"

CourseCode = Annotated[str, Field(pattern=COURSE_CODE_PATTERN, examples=["CMSC 14100"])]
TermId = Annotated[str, Field(pattern=TERM_ID_PATTERN, examples=["2026-AU"])]
#: Absolute term ("2028-SP") or plan-relative term ("Y2-SP" = Spring of the 2nd plan year).
TermRef = Annotated[str, Field(pattern=TERM_REF_PATTERN, examples=["Y2-SP", "2028-SP"])]
CatalogYear = Annotated[str, Field(pattern=CATALOG_YEAR_PATTERN, examples=["2026-27"])]
Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]
NodeId = Annotated[str, Field(pattern=NODE_ID_PATTERN)]
Quarter = Literal["AU", "WI", "SP", "SU"]
STANDINGS = ("first-year", "second-year", "third-year", "fourth-year")


class Model(BaseModel):
    """Base: unknown keys are errors (catches YAML typos); aliases used on output."""

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


def _exactly_one(obj: object, *names: str) -> None:
    present = [n for n in names if getattr(obj, n) is not None]
    if len(present) != 1:
        raise ValueError(f"exactly one of {', '.join(names)} is required (got {present or 'none'})")


# --------------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------------


class Source(Model):
    """Where a rule came from. `quote` is copied verbatim from the page."""

    url: str | None = None
    snapshot_id: str | None = None
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def _needs_location(self) -> Self:
        if self.url is None and self.snapshot_id is None:
            raise ValueError("source needs a url or a snapshot_id")
        return self


# --------------------------------------------------------------------------------------------
# Prerequisite expressions
# --------------------------------------------------------------------------------------------

AtomKind = Literal["course", "concurrent", "placement", "standing", "program", "consent"]
ATOM_KINDS: tuple[str, ...] = (
    "course",
    "concurrent",
    "placement",
    "standing",
    "program",
    "consent",
)


class Atom(Model):
    """`course`: met by a course completed, credited or planned in a strictly earlier term.
    `concurrent`: same or earlier term. `placement`/`standing`: plan facts.
    `program`: enrolment restriction (glob on program ids, e.g. `cmsc-*`).
    `consent`: never blocks; always produces a warning."""

    kind: AtomKind
    value: str = Field(min_length=1)
    min_grade: str | None = None

    @model_validator(mode="after")
    def _check_value(self) -> Self:
        import re

        if self.kind in ("course", "concurrent") and not re.match(COURSE_CODE_PATTERN, self.value):
            raise ValueError(f"{self.kind} atom needs a course code, got {self.value!r}")
        if self.kind == "standing" and self.value not in STANDINGS:
            raise ValueError(f"standing must be one of {STANDINGS}, got {self.value!r}")
        if self.min_grade is not None and self.kind != "course":
            raise ValueError("min_grade only applies to course atoms")
        return self


class Expr(Model):
    """Canonical form: `{op, n, children, atom}`. Shorthand accepted on input:
    `"CMSC 14100"`, `{course: X, min_grade: G}`, `{concurrent: X}`, `{placement: X}`,
    `{standing: X}`, `{program: X}`, `{consent: X}`, `{all: [...]}`, `{any: [...]}`,
    `{n_of: k, of: [...]}`."""

    op: Literal["all", "any", "n_of", "atom"]
    n: int | None = None
    children: list[Expr] = Field(default_factory=list)
    atom: Atom | None = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"op": "atom", "atom": {"kind": "course", "value": data}}
        if not isinstance(data, dict) or "op" in data:
            return data
        if "all" in data or "any" in data:
            key = "all" if "all" in data else "any"
            if set(data) != {key}:
                raise ValueError(f"'{key}' takes no other keys")
            return {"op": key, "children": data[key]}
        if "n_of" in data:
            if set(data) != {"n_of", "of"}:
                raise ValueError("'n_of' needs exactly the keys n_of and of")
            return {"op": "n_of", "n": data["n_of"], "children": data["of"]}
        kinds = [k for k in ATOM_KINDS if k in data]
        if len(kinds) == 1:
            kind = kinds[0]
            extra = set(data) - {kind, "min_grade"}
            if extra:
                raise ValueError(f"unexpected keys in {kind} atom: {sorted(extra)}")
            atom = {"kind": kind, "value": data[kind]}
            if "min_grade" in data:
                atom["min_grade"] = data["min_grade"]
            return {"op": "atom", "atom": atom}
        raise ValueError(f"cannot read expression {data!r}")

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.op == "atom":
            if self.atom is None or self.children or self.n is not None:
                raise ValueError("atom expressions carry only `atom`")
        else:
            if self.atom is not None or not self.children:
                raise ValueError(f"'{self.op}' needs children and no atom")
            if self.op == "n_of":
                if self.n is None or not 1 <= self.n <= len(self.children):
                    raise ValueError("n_of needs 1 <= n <= len(children)")
            elif self.n is not None:
                raise ValueError(f"'{self.op}' takes no n")
        return self


# --------------------------------------------------------------------------------------------
# Program rule trees
# --------------------------------------------------------------------------------------------


class Selector(Model):
    """Which catalog courses a node may draw from.

    A course matches when it is not in `exclude` (by cross-list group) and every criterion that
    is set holds: `codes` (any listed code, by cross-list group), `subject`, `number_range`
    (inclusive, on the 5-digit number), `tags` (has any), `list` (member of the named
    `course_list`, sublists included), `union` (matches at least one sub-selector).

    A course's tag set is `tags` plus `"core:" + t` for each of its `core_tags`, so
    `tags: ["core:arts"]` matches a course whose `core_tags` contains `arts`."""

    codes: list[CourseCode] = Field(default_factory=list)
    subject: str | None = Field(default=None, pattern=r"^[A-Z]{2,5}$")
    number_range: tuple[int, int] | None = None
    tags: list[str] = Field(default_factory=list)
    list_: str | None = Field(default=None, alias="list")
    union: list[Selector] = Field(default_factory=list)
    exclude: list[CourseCode] = Field(default_factory=list)

    @model_validator(mode="after")
    def _has_criterion(self) -> Self:
        positive = self.codes or self.subject or self.number_range or self.tags or self.list_
        if not positive and not self.union:
            raise ValueError("selector needs at least one criterion")
        if self.number_range is not None and self.number_range[0] > self.number_range[1]:
            raise ValueError("number_range must be [low, high]")
        return self


class MaxFrom(Model):
    """At most `n` of the node's courses may match `selector` ("at most 2 from outside CMSC").

    With `as_enrolled`, a course counts only when the code the student enrolled under matches
    the selector's subject, number range and tags: a course cross-listed as CMSC 23500 /
    CMSC 33550 and taken as CMSC 33550 is not "from the 20000 level"."""

    selector: Selector
    n: int = Field(ge=0)
    as_enrolled: bool = False
    #: The sentence stating the cap (the seed requires it).
    source: Source | None = None


class Constraints(Model):
    min_grade: str | None = None
    no_pass_fail: bool = False
    #: All courses used by this node come from one sequence (one sublist of the selector's list).
    same_sequence: bool = False
    in_order: bool = False
    max_from: list[MaxFrom] = Field(default_factory=list)
    distinct_subjects: int | None = Field(default=None, ge=1)
    #: SPEC: "each course fills at most one node, unless the rule says otherwise".
    allow_double_count: bool = False

    @model_validator(mode="before")
    @classmethod
    def _max_from_single(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("max_from"), dict):
            data = {**data, "max_from": [data["max_from"]]}
        return data


class NodeBase(Model):
    #: Missing ids are filled with the 1-based position among siblings ("intro/1").
    id: NodeId | None = None
    label: str | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    source: Source | None = None
    needs_review: bool = False
    #: Weight in objective 1 (maximize weighted satisfied nodes).
    weight: float = Field(default=1.0, gt=0)


class SlotNode(NodeBase):
    """One specific course or alternatives."""

    kind: Literal["slot"] = "slot"
    any_of: list[CourseCode] = Field(min_length=1)


class SelectNode(NodeBase):
    """Choose `count` courses (or `units` units) from a selector."""

    kind: Literal["select"] = "select"
    count: int | None = Field(default=None, ge=1)
    units: int | None = Field(default=None, ge=1)
    from_: Selector = Field(alias="from")

    @model_validator(mode="after")
    def _count_or_units(self) -> Self:
        _exactly_one(self, "count", "units")
        return self


class GroupNode(NodeBase):
    """Children combined: all of them (`all: true`) or at least `n_of`."""

    kind: Literal["group"] = "group"
    all: bool = False
    n_of: int | None = Field(default=None, ge=1)
    children: list[Node] = Field(min_length=1)

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.all == (self.n_of is not None):
            raise ValueError("group needs exactly one of `all: true` or `n_of`")
        if self.n_of is not None and self.n_of > len(self.children):
            raise ValueError("n_of exceeds the number of children")
        for i, child in enumerate(self.children, start=1):
            if child.id is None:
                child.id = str(i)
        ids = [c.id for c in self.children]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate child ids: {ids}")
        return self


class Part(Model):
    """One part of a bounded_parts node, e.g. `{id: huma, from: {list: ...}, count: [2, 3]}`."""

    id: NodeId
    label: str | None = None
    from_: Selector = Field(alias="from")
    count: tuple[int, int]
    constraints: Constraints = Field(default_factory=Constraints)
    source: Source | None = None
    needs_review: bool = False

    @model_validator(mode="before")
    @classmethod
    def _inline_constraints(cls, data: Any) -> Any:
        if isinstance(data, dict):
            inline = {k: data[k] for k in Constraints.model_fields if k in data}
            if inline:
                rest = {k: v for k, v in data.items() if k not in inline}
                merged = {**dict(rest.get("constraints", {})), **inline}
                return {**rest, "constraints": merged}
        return data

    @model_validator(mode="after")
    def _range(self) -> Self:
        lo, hi = self.count
        if lo < 0 or lo > hi:
            raise ValueError("count must be [min, max] with 0 <= min <= max")
        return self


class Total(Model):
    courses: int | None = Field(default=None, ge=1)
    units: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _one(self) -> Self:
        _exactly_one(self, "courses", "units")
        return self


class BoundedPartsNode(NodeBase):
    """Parts with [min, max] counts that sum to a total."""

    kind: Literal["bounded_parts"] = "bounded_parts"
    total: Total
    parts: list[Part] = Field(min_length=1)

    @model_validator(mode="after")
    def _feasible(self) -> Self:
        ids = [p.id for p in self.parts]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate part ids: {ids}")
        if self.total.courses is not None:
            lo = sum(p.count[0] for p in self.parts)
            hi = sum(p.count[1] for p in self.parts)
            if not lo <= self.total.courses <= hi:
                raise ValueError(f"total {self.total.courses} outside part bounds [{lo}, {hi}]")
        return self


NODE_KINDS = ("group", "slot", "select", "bounded_parts")


def _node_shorthand(data: Any) -> Any:
    """`{id: x, group: {...}}` -> `{id: x, kind: group, ...}` (the spec's YAML form)."""
    if isinstance(data, dict) and "kind" not in data:
        present = [k for k in NODE_KINDS if k in data]
        if len(present) != 1:
            raise ValueError(f"node needs exactly one of {NODE_KINDS}; got keys {sorted(data)}")
        kind = present[0]
        inner = data[kind]
        if not isinstance(inner, dict):
            raise ValueError(f"'{kind}' must map to an object")
        outer = {k: v for k, v in data.items() if k != kind}
        clash = set(outer) & set(inner)
        if clash:
            raise ValueError(f"keys given twice: {sorted(clash)}")
        return {"kind": kind, **outer, **inner}
    return data


Node = Annotated[
    Annotated[GroupNode | SlotNode | SelectNode | BoundedPartsNode, Field(discriminator="kind")],
    BeforeValidator(_node_shorthand),
]


# --------------------------------------------------------------------------------------------
# Program-level policy and programs
# --------------------------------------------------------------------------------------------


class ShareLimit(Model):
    """At most `max` courses shared with programs matching `with` (`type:minor`, `core`,
    `program:<id>`), not counting nodes/parts named in `except` (e.g. `language`)."""

    with_: str = Field(alias="with", min_length=1)
    max: int = Field(ge=0)
    except_: list[str] = Field(default_factory=list, alias="except")
    #: The sentence stating the limit (the seed requires it).
    source: Source | None = None


class Residency(Model):
    min_fraction: float = Field(gt=0, le=1)
    source: Source | None = None


class Timing(Model):
    apply_by: TermRef | None = None
    complete_by: TermRef | None = None
    #: Course codes that must be complete before `apply_by` (Bx/MS application prerequisites).
    apply_requires: list[CourseCode] = Field(default_factory=list)
    source: Source | None = None


class Policy(Model):
    share: list[ShareLimit] = Field(default_factory=list)
    residency: Residency | None = None
    timing: Timing | None = None
    #: Program ids (globs allowed) this program requires, e.g. Bx/MS requires its major.
    requires: list[str] = Field(default_factory=list)
    #: Program ids this program cannot be combined with.
    excludes: list[str] = Field(default_factory=list)
    #: Sentences stating `requires` / `excludes` (required by the seed when the list is set).
    requires_source: Source | None = None
    excludes_source: Source | None = None


ProgramType = Literal[
    "major",
    "minor",
    "bxms",
    "joint",
    "specialization",
    "track",
    "preprofessional",
    "study_abroad_block",
    "core",
]
Degree = Literal["BA", "BS", "MS", "MA"]


class ProgramRules(Model):
    """One program version as the verifier sees it. Node paths are `<id>/<child id>/...`."""

    id: Slug
    catalog_year: CatalogYear
    type: ProgramType | None = None
    rules: Node
    policy: Policy = Field(default_factory=Policy)


class OverloadReason(Model):
    """A reason that permits a 500-unit quarter (SPEC V05). Conditions are optional; when set,
    the verifier checks them (plan year, a course in that term matching a selector, or a course
    of at least `min_course_units`)."""

    id: Slug
    label: str
    year: int | None = Field(default=None, ge=1, le=6)
    course_selector: Selector | None = None
    min_course_units: int | None = None
    source: Source | None = None


class CollegePolicy(Model):
    """College-wide rules. Every non-null value needs an entry in `sources` keyed by field
    name; null means "not encoded yet" and the related check reports it as an assumption."""

    catalog_year: CatalogYear
    total_units: int | None = None
    units_by_enrollment: int | None = None
    full_time_min_units: int | None = None
    full_time_max_units: int | None = None
    overload_units: int | None = None
    overload_reasons: list[OverloadReason] = Field(default_factory=list)
    core_program_id: Slug = "core"
    #: Path of the Language Competence node inside the core program, if any.
    language_node: str | None = None
    core_complete_by: TermRef | None = None
    #: Plan year in which a civilization sequence taken abroad may still finish the Core.
    civ_abroad_year: int | None = None
    residency_min_fraction: float | None = None
    max_quarters: int | None = None
    sources: dict[str, Source] = Field(default_factory=dict)
    needs_review: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sourced(self) -> Self:
        scalar = (
            "total_units",
            "units_by_enrollment",
            "full_time_min_units",
            "full_time_max_units",
            "overload_units",
            "core_complete_by",
            "civ_abroad_year",
            "residency_min_fraction",
            "max_quarters",
        )
        missing = [f for f in scalar if getattr(self, f) is not None and f not in self.sources]
        if missing:
            raise ValueError(f"college policy values without a source: {missing}")
        return self


class Requisite(Model):
    course: CourseCode
    prereq: Expr | None = None
    coreq: Expr | None = None
    restrictions: Expr | None = None
    #: The catalog sentence the rule came from, verbatim.
    raw_text: str | None = None
    source: Source | None = None
    needs_review: bool = False


class RuleSet(Model):
    catalog_year: CatalogYear
    programs: list[ProgramRules] = Field(default_factory=list)
    college: CollegePolicy | None = None
    requisites: list[Requisite] = Field(default_factory=list)


# --------------------------------------------------------------------------------------------
# Catalog facts the verifier reads
# --------------------------------------------------------------------------------------------


class Course(Model):
    code: CourseCode
    title: str
    units: int = Field(default=100, ge=0)
    description: str | None = None
    core_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    repeatable: bool = False
    source: Source | None = None

    @property
    def subject(self) -> str:
        return self.code.split(" ")[0]

    @property
    def number(self) -> int:
        return int(self.code.split(" ")[1])


class CourseList(Model):
    """A named list per catalog year. Members = `courses` plus every course of `sublists`.
    A list of sequences (e.g. `core-huma-sequences`) has one sublist per sequence."""

    name: Slug
    label: str | None = None
    courses: list[CourseCode] = Field(default_factory=list)
    sublists: list[Slug] = Field(default_factory=list)
    source: Source | None = None
    needs_review: bool = False


class CourseRelation(Model):
    a: CourseCode
    b: CourseCode
    kind: Literal["equivalent", "mutually_exclusive", "replaces"]
    source: Source | None = None


class OfferingPattern(Model):
    course: CourseCode
    quarter: Quarter
    p_offered: float = Field(ge=0, le=1)
    evidence_terms: list[TermId] = Field(default_factory=list)
    method: str = "history"


class Meeting(Model):
    days: list[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]] = Field(min_length=1)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")


class Section(Model):
    term: TermId
    course: CourseCode
    section_no: str
    component: str | None = None
    instructor_ids: list[str] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)
    status: str | None = None


class Term(Model):
    id: TermId
    start: dt.date | None = None
    end: dt.date | None = None


AttributeKey = Literal[
    "workload_hours",
    "difficulty",
    "intellectual_intensity",
    "pace",
    "grading_strictness",
    "recommend_rate",
]


class AttributeValue(Model):
    subject_type: Literal["course", "course_instructor"] = "course"
    subject_id: str
    key: AttributeKey
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    n: int = 0
    #: A cold-start estimate is a `prior` (SPEC "A3"), labelled as an estimate in the UI.
    method: Literal["prior", "forum", "blend"] = "prior"


class Catalog(Model):
    catalog_year: CatalogYear
    courses: list[Course] = Field(default_factory=list)
    #: Cross-listed codes; each group counts as one course.
    crosslist_groups: list[list[CourseCode]] = Field(default_factory=list)
    relations: list[CourseRelation] = Field(default_factory=list)
    course_lists: list[CourseList] = Field(default_factory=list)
    terms: list[Term] = Field(default_factory=list)
    offerings: list[OfferingPattern] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    attributes: list[AttributeValue] = Field(default_factory=list)


# --------------------------------------------------------------------------------------------
# Plans and goals
# --------------------------------------------------------------------------------------------

ItemStatus = Literal["planned", "in_progress", "completed", "transfer", "exam"]
Grading = Literal["letter", "pass_fail"]


class PlanItem(Model):
    """A course (or an unfilled requirement slot, `slot_ref` = node path) in a term."""

    id: str | None = None
    course: CourseCode | None = None
    slot_ref: str | None = None
    term: TermId
    status: ItemStatus = "planned"
    locked: bool = False
    #: Overrides the catalog units (variable-unit courses).
    units: int | None = Field(default=None, ge=0)
    grading: Grading = "letter"
    #: Grade earned, for completed courses only (checked against min_grade).
    grade: str | None = None

    @model_validator(mode="after")
    def _course_or_slot(self) -> Self:
        _exactly_one(self, "course", "slot_ref")
        return self


class Credit(Model):
    kind: Literal["AP", "placement", "transfer"]
    label: str
    maps_to: CourseCode | None = None
    units: int = Field(default=0, ge=0)


class PlanProgram(Model):
    program_id: Slug
    #: The program_version id this plan is bound to (SPEC "Versioning"); None = current published.
    version_id: int | None = None
    options: dict[str, str] = Field(default_factory=dict)


class GoalBase(Model):
    id: str = Field(min_length=1)
    scope: Literal["career", "term"] = "career"
    term: TermId | None = None
    hard: bool = False
    weight: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def _scope_term(self) -> Self:
        if (self.scope == "term") != (self.term is not None):
            raise ValueError("term-scoped goals need `term`; career goals must not set it")
        return self


class CourseLoadGoal(GoalBase):
    type: Literal["course_load"] = "course_load"
    min_courses: int | None = Field(default=None, ge=0)
    max_courses: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.min_courses is None and self.max_courses is None:
            raise ValueError("course_load needs min_courses or max_courses")
        return self


class WorkloadHoursGoal(GoalBase):
    type: Literal["workload_hours"] = "workload_hours"
    max_hours: float = Field(gt=0)
    aggregate: Literal["per_term", "career_average"] = "per_term"
    #: Use the upper confidence bound of each course's workload.
    strict: bool = False


class DifficultyCapGoal(GoalBase):
    type: Literal["difficulty_cap"] = "difficulty_cap"
    max_index: float | None = None
    max_very_hard: int | None = Field(default=None, ge=0)
    very_hard_threshold: float | None = None

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.max_index is None and self.max_very_hard is None:
            raise ValueError("difficulty_cap needs max_index or max_very_hard")
        return self


class ChallengeGoal(GoalBase):
    type: Literal["challenge"] = "challenge"
    min_index: float


class ProtectGpaGoal(GoalBase):
    type: Literal["protect_gpa"] = "protect_gpa"
    #: A course is "high grading_strictness" at or above this value.
    strictness_threshold: float | None = None


class GraduateByGoal(GoalBase):
    type: Literal["graduate_by"] = "graduate_by"
    by_term: TermRef


class StudyAbroadGoal(GoalBase):
    type: Literal["study_abroad"] = "study_abroad"
    program_id: Slug
    abroad_term: TermRef


class BxmsGoal(GoalBase):
    type: Literal["bxms"] = "bxms"
    program_id: Slug
    apply_by: TermRef


class PremedGoal(GoalBase):
    type: Literal["premed"] = "premed"
    courses: list[CourseCode] = Field(default_factory=list)
    list_: str | None = Field(default=None, alias="list")
    complete_by: TermRef

    @model_validator(mode="after")
    def _courses(self) -> Self:
        if not self.courses and self.list_ is None:
            raise ValueError("premed needs courses or a list")
        return self


class InterestGoal(GoalBase):
    type: Literal["interest"] = "interest"
    tags: list[str] = Field(min_length=1)
    min_share: float | None = Field(default=None, ge=0, le=1)


class LightQuarterGoal(GoalBase):
    type: Literal["light_quarter"] = "light_quarter"
    scope: Literal["term"] = "term"
    max_courses: int = Field(ge=0)


class LanguageGoal(GoalBase):
    type: Literal["language"] = "language"
    language: str
    level: str
    by_term: TermRef
    courses: list[CourseCode] = Field(default_factory=list)
    list_: str | None = Field(default=None, alias="list")


Goal = Annotated[
    CourseLoadGoal
    | WorkloadHoursGoal
    | DifficultyCapGoal
    | ChallengeGoal
    | ProtectGpaGoal
    | GraduateByGoal
    | StudyAbroadGoal
    | BxmsGoal
    | PremedGoal
    | InterestGoal
    | LightQuarterGoal
    | LanguageGoal,
    Field(discriminator="type"),
]


class PlanState(Model):
    catalog_year: CatalogYear
    entry_term: TermId
    #: Class standing at entry: 1 for first-years, 2 for most transfers.
    entry_year_level: int = Field(default=1, ge=1, le=4)
    items: list[PlanItem] = Field(default_factory=list)
    credits: list[Credit] = Field(default_factory=list)
    programs: list[PlanProgram] = Field(default_factory=list)
    goals: list[Goal] = Field(default_factory=list)
    #: Placement results (values matched by `placement` atoms), e.g. "MATH 15100".
    placements: list[str] = Field(default_factory=list)
    #: term -> OverloadReason.id claimed for a 500-unit quarter.
    overload_reasons: dict[TermId, Slug] = Field(default_factory=dict)


# --------------------------------------------------------------------------------------------
# Verifier output
# --------------------------------------------------------------------------------------------

IssueCode = Literal[
    "V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08", "V09", "V10", "V11", "V12"
]
IssueLevel = Literal["error", "warning", "info"]


class Issue(Model):
    code: IssueCode
    level: IssueLevel
    message: str
    course_ids: list[CourseCode] = Field(default_factory=list)
    term_ids: list[TermId] = Field(default_factory=list)
    node_id: str | None = None
    goal_id: str | None = None
    fix_hints: list[str] = Field(default_factory=list)


class Assignment(Model):
    node: str
    courses: list[CourseCode]


class PrereqWitness(Model):
    """`by` entries: `"CODE@TERM"` (a plan item), `"credit:CODE"`, `"placement:VALUE"`,
    `"standing:VALUE"`, `"program:ID"` or `"consent:VALUE"`."""

    course: CourseCode
    term: TermId
    by: list[str]


class LoadEntry(Model):
    term: TermId
    units: int


class GoalResult(Model):
    goal: str
    value: float | None = None
    limit: float | None = None
    pass_: bool = Field(alias="pass")


class Certificate(Model):
    plan_hash: str
    #: "<program id>@<catalog year>" -> rules hash (see planner_core.hashing.rules_hash).
    rules: dict[str, str]
    assignments: list[Assignment] = Field(default_factory=list)
    prereq_witnesses: list[PrereqWitness] = Field(default_factory=list)
    loads: list[LoadEntry] = Field(default_factory=list)
    goals: list[GoalResult] = Field(default_factory=list)


class NodeProgress(Model):
    """Per-node progress for the planner's requirement rail."""

    program_id: str
    node_id: str
    label: str | None = None
    satisfied: bool
    have: int
    need: int
    unit: Literal["courses", "units"] = "courses"
    courses: list[CourseCode] = Field(default_factory=list)


class Report(Model):
    status: Literal["valid", "warnings", "errors"]
    plan_hash: str
    core_version: str
    issues: list[Issue] = Field(default_factory=list)
    #: Present when there are no errors; the plan is "valid" only if check_certificate accepts it.
    certificate: Certificate | None = None
    progress: list[NodeProgress] = Field(default_factory=list)
    #: E.g. "planned courses are assumed to meet grade minimums".
    assumptions: list[str] = Field(default_factory=list)


class VerifyOptions(Model):
    strictness: Literal["normal", "strict"] = "normal"
    include_certificate: bool = True
    solver_time_limit_s: float = Field(default=2.0, gt=0)
    #: Run only these checks (None = all V01-V12). Golden plans that test one program in
    #: isolation use this to skip, e.g., graduation totals (V09) and quarter loads (V05).
    checks: list[IssueCode] | None = None


# --------------------------------------------------------------------------------------------
# Change sets
# --------------------------------------------------------------------------------------------


class ItemTarget(Model):
    """Identifies an existing item by `item_id`, `course` or `slot_ref` (exactly one).
    `term` disambiguates repeatable courses."""

    item_id: str | None = None
    course: CourseCode | None = None
    slot_ref: str | None = None

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        _exactly_one(self, "item_id", "course", "slot_ref")
        return self


class AddOp(Model):
    op: Literal["add"] = "add"
    course: CourseCode | None = None
    slot_ref: str | None = None
    term: TermId
    status: ItemStatus = "planned"
    units: int | None = None
    grading: Grading = "letter"
    locked: bool = False

    @model_validator(mode="after")
    def _course_or_slot(self) -> Self:
        _exactly_one(self, "course", "slot_ref")
        return self


class MoveOp(ItemTarget):
    op: Literal["move"] = "move"
    from_term: TermId | None = None
    to_term: TermId


class RemoveOp(ItemTarget):
    op: Literal["remove"] = "remove"
    term: TermId | None = None


class LockOp(ItemTarget):
    op: Literal["lock"] = "lock"
    term: TermId | None = None


class UnlockOp(ItemTarget):
    op: Literal["unlock"] = "unlock"
    term: TermId | None = None


ChangeOp = Annotated[AddOp | MoveOp | RemoveOp | LockOp | UnlockOp, Field(discriminator="op")]


class ChangeSet(Model):
    id: str | None = None
    plan_id: str | None = None
    origin: Literal["generate", "chat", "user"]
    ops: list[ChangeOp] = Field(min_length=1)
    base_plan_hash: str
    preview_report: Report | None = None
    status: Literal["proposed", "applied", "discarded", "stale"] = "proposed"


GroupNode.model_rebuild()
ProgramRules.model_rebuild()


# --------------------------------------------------------------------------------------------
# Plan generator (prompt 06)
# --------------------------------------------------------------------------------------------


class GenerateOptions(Model):
    """The Generate-plan form as the deterministic generator reads it (SPEC "Generate-plan
    popup"). Locked and completed courses are always kept."""

    scope: Literal["whole", "remaining", "selected"] = "whole"
    selected_terms: list[TermId] = Field(default_factory=list)
    #: The current term: no course is placed before it ("remaining" starts here).
    today_term: TermId | None = None
    #: Career-wide load: -1 lighter (spread courses evenly) ... +1 heavier (finish sooner).
    load: float = Field(default=0.0, ge=-1, le=1)
    per_term_load: dict[TermId, float] = Field(default_factory=dict)
    max_courses_per_term: int | None = Field(default=None, ge=1, le=6)
    #: Use a 500-unit quarter where the plan already claims an overload reason that applies.
    allow_overload: bool = False
    #: Goals to plan for; None = the plan's own goals.
    goals: list[Goal] | None = None
    interests: list[str] = Field(default_factory=list)
    variants: int = Field(default=2, ge=1, le=3)
    #: Courses the student accepts in quarters where they are rarely offered (p_offered < 0.3).
    allow_rarely_offered: list[CourseCode] = Field(default_factory=list)
    #: Course preferences from the plan-generator agent (prompt 07): code -> 0..100.
    #: None = the default preferences (interest tags, then recommend_rate, then level).
    preferences: dict[CourseCode, int] | None = None
    #: Wall-clock budget of the solver for the whole generation (all variants): the first
    #: variant gets half, the others share the rest.
    time_limit_s: float = Field(default=4.0, gt=0, le=30)


class Conflict(Model):
    """One goal or limit in the smallest set that makes a request impossible."""

    id: str
    kind: Literal[
        "program", "goal", "graduation", "offering", "load", "courses_per_term", "locked", "sharing"
    ]
    label: str


class Infeasibility(Model):
    #: Plain English, e.g. "Graduating by Spring 2029 needs 5 more courses than your
    #: remaining quarters allow."
    message: str
    conflicts: list[Conflict] = Field(default_factory=list)


class Variant(Model):
    label: str
    #: The plan after the change; verified, and its certificate accepted by the checker.
    plan: PlanState
    #: The operations that turn the current plan into `plan` (`apply_ops`).
    ops: list[ChangeOp]
    report: Report
    metrics: dict[str, float] = Field(default_factory=dict)
    #: term -> one-line rationale (written by the agent in prompt 07; empty here).
    rationale: dict[TermId, str] = Field(default_factory=dict)


class GenerateResult(Model):
    variants: list[Variant] = Field(default_factory=list)
    #: Set when no plan meets the request.
    infeasible: Infeasibility | None = None
    #: Variants dropped because `verify` or `check_certificate` rejected them (a bug).
    alerts: list[str] = Field(default_factory=list)
