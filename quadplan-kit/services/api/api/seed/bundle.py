"""Read one catalog year of seed YAML, check its integrity, and build planner_core inputs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from api.seed.models import CourseListsFile, CoursesFile, ProgramSeed, SeedCourse, TermsFile
from planner_core.dsl import expr_courses, iter_nodes, iter_parts
from planner_core.models import (
    Catalog,
    CollegePolicy,
    Course,
    CourseList,
    CourseRelation,
    Expr,
    OfferingPattern,
    Requisite,
    RuleSet,
    Selector,
    SlotNode,
    Term,
)
from pydantic import ValidationError

YEAR_DIR = re.compile(r"^\d{4}-\d{2}$")
#: "Terms Offered" -> p_offered (docs/CONTRACTS.md; open question in docs/OPEN_QUESTIONS.md).
P_LISTED, P_UNLISTED = 0.95, 0.05


class SeedError(Exception):
    """A seed file is missing, unreadable or fails validation."""


@dataclass
class SeedBundle:
    catalog_year: str
    courses: list[SeedCourse] = field(default_factory=list)
    terms: list[Term] = field(default_factory=list)
    course_lists: list[CourseList] = field(default_factory=list)
    programs: list[ProgramSeed] = field(default_factory=list)
    college: CollegePolicy | None = None


def _read(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SeedError(f"{path}: invalid YAML: {exc}") from exc


def _parse[T](model: type[T], path: Path) -> T:
    try:
        return model.model_validate(_read(path))  # type: ignore[attr-defined]
    except ValidationError as exc:
        raise SeedError(f"{path}: {exc}") from exc


def discover(seed_root: Path) -> list[Path]:
    """Catalog-year directories (`2026-27`) under `seed_root`."""
    if not seed_root.is_dir():
        return []
    return sorted(p for p in seed_root.iterdir() if p.is_dir() and YEAR_DIR.match(p.name))


def load_bundle(year_dir: Path) -> SeedBundle:
    bundle = SeedBundle(catalog_year=year_dir.name)
    course_files = [year_dir / "courses.yaml", *sorted((year_dir / "courses").glob("*.yaml"))]
    for path in course_files:
        if path.exists():
            bundle.courses += _parse(CoursesFile, path).courses
    if (path := year_dir / "terms.yaml").exists():
        bundle.terms = _parse(TermsFile, path).terms
    if (path := year_dir / "course_lists.yaml").exists():
        bundle.course_lists = _parse(CourseListsFile, path).course_lists
    if (path := year_dir / "college_policy.yaml").exists():
        bundle.college = _parse(CollegePolicy, path)
    for path in sorted((year_dir / "programs").glob("*.yaml")):
        bundle.programs.append(_parse(ProgramSeed, path))
    return bundle


def _selector_refs(sel: Selector) -> tuple[set[str], set[str]]:
    codes, lists = set(sel.codes) | set(sel.exclude), {sel.list_} if sel.list_ else set()
    for sub in sel.union:
        c, lst = _selector_refs(sub)
        codes, lists = codes | c, lists | lst
    return codes, lists


def _dupes(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    return sorted({v for v in values if v in seen or seen.add(v)})  # type: ignore[func-returns-value]


def integrity(bundle: SeedBundle) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors block loading; warnings are printed."""
    errors: list[str] = []
    warnings: list[str] = []
    year = bundle.catalog_year
    codes = {c.code for c in bundle.courses}
    lists = {cl.name for cl in bundle.course_lists}
    errors += [f"duplicate course {c}" for c in _dupes(c.code for c in bundle.courses)]
    errors += [f"duplicate course list {n}" for n in _dupes(cl.name for cl in bundle.course_lists)]
    errors += [f"duplicate program {p}" for p in _dupes(p.id for p in bundle.programs)]

    for course in bundle.courses:
        for kind in ("crosslists", "equivalents", "mutually_exclusive", "replaces"):
            for ref in getattr(course, kind):
                if ref not in codes:
                    errors.append(f"course {course.code}: {kind} names unknown course {ref}")
        for kind in ("prereq", "coreq", "restrictions"):
            expr: Expr | None = getattr(course, kind)
            for ref in sorted(expr_courses(expr) - codes) if expr else []:
                warnings.append(f"course {course.code}: {kind} names {ref}, not in the seed")

    for cl in bundle.course_lists:
        errors += [
            f"course list {cl.name}: unknown course {c}" for c in cl.courses if c not in codes
        ]
        errors += [
            f"course list {cl.name}: unknown sublist {s}" for s in cl.sublists if s not in lists
        ]
        if cl.source is None:
            errors.append(f"course list {cl.name}: missing source")

    for program in bundle.programs:
        if program.catalog_year != year:
            errors.append(f"program {program.id}: catalog_year {program.catalog_year} != {year}")
        for path, node in [*iter_nodes(program), *iter_parts(program)]:
            if node.source is None:
                errors.append(f"{path}: missing source (every rule node needs a verbatim quote)")
            refs: tuple[set[str], set[str]] = (set(), set())
            if isinstance(node, SlotNode):
                refs = (set(node.any_of), set())
            elif (selector := getattr(node, "from_", None)) is not None:
                refs = _selector_refs(selector)
            for mf in node.constraints.max_from:
                c, lst = _selector_refs(mf.selector)
                refs = (refs[0] | c, refs[1] | lst)
            errors += [f"{path}: unknown course {c}" for c in sorted(refs[0] - codes)]
            errors += [f"{path}: unknown course list {n}" for n in sorted(refs[1] - lists)]

    if bundle.college is not None:
        if bundle.college.catalog_year != year:
            errors.append(f"college_policy: catalog_year {bundle.college.catalog_year} != {year}")
        for reason in bundle.college.overload_reasons:
            if reason.course_selector is not None:
                c, lst = _selector_refs(reason.course_selector)
                errors += [
                    f"overload reason {reason.id}: unknown course {x}" for x in sorted(c - codes)
                ]
                errors += [
                    f"overload reason {reason.id}: unknown list {x}" for x in sorted(lst - lists)
                ]
    return errors, warnings


def _crosslist_groups(courses: list[SeedCourse]) -> list[list[str]]:
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for course in courses:
        for other in course.crosslists:
            parent[find(course.code)] = find(other)
    groups: dict[str, set[str]] = {}
    for code in list(parent):
        groups.setdefault(find(code), set()).add(code)
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


def build_catalog(bundle: SeedBundle) -> Catalog:
    relations: dict[tuple[str, str, str], CourseRelation] = {}
    offerings: list[OfferingPattern] = []
    for c in bundle.courses:
        for kind, refs in (
            ("equivalent", c.equivalents),
            ("mutually_exclusive", c.mutually_exclusive),
            ("replaces", c.replaces),
        ):
            for ref in refs:
                a, b = (c.code, ref) if kind == "replaces" else tuple(sorted((c.code, ref)))
                relations.setdefault(
                    (a, b, kind), CourseRelation(a=a, b=b, kind=kind, source=c.source)
                )
        if c.terms_offered:
            quarters = ["AU", "WI", "SP"] + (["SU"] if "SU" in c.terms_offered else [])
            for q in quarters:
                p = P_LISTED if q in c.terms_offered else P_UNLISTED
                offerings.append(
                    OfferingPattern(course=c.code, quarter=q, p_offered=p, method="catalog")
                )
    return Catalog(
        catalog_year=bundle.catalog_year,
        courses=[
            Course(
                code=c.code,
                title=c.title,
                units=c.units,
                description=c.description,
                core_tags=c.core_tags,
                tags=c.tags,
                repeatable=c.repeatable,
                source=c.source,
            )
            for c in bundle.courses
        ],
        crosslist_groups=_crosslist_groups(bundle.courses),
        relations=sorted(relations.values(), key=lambda r: (r.a, r.b, r.kind)),
        course_lists=bundle.course_lists,
        terms=bundle.terms,
        offerings=offerings,
    )


def build_requisites(bundle: SeedBundle) -> list[Requisite]:
    return [
        Requisite(
            course=c.code,
            prereq=c.prereq,
            coreq=c.coreq,
            restrictions=c.restrictions,
            raw_text=c.prereq_text,
            source=c.source,
            needs_review=c.needs_review,
        )
        for c in bundle.courses
        if c.prereq or c.coreq or c.restrictions or c.prereq_text
    ]


def build_rules(bundle: SeedBundle, program_ids: Iterable[str] | None = None) -> RuleSet:
    wanted = set(program_ids) if program_ids is not None else {p.id for p in bundle.programs}
    return RuleSet(
        catalog_year=bundle.catalog_year,
        programs=[p.rules_only() for p in bundle.programs if p.id in wanted],
        college=bundle.college,
        requisites=build_requisites(bundle),
    )
