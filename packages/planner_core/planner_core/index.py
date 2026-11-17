"""Lookup tables shared by the checks, the solver model and the certificate checker.

`Index` answers questions about catalog facts (is this code known, which cross-list group is
it in, does it match a selector, which sequences does a list define). `PlanFacts` answers
questions about the plan (what was taken when, which items carry load). Both are plain
dictionaries built once per `verify` call; nothing here decides whether a plan is valid.

Semantics fixed here (see docs/CONTRACTS.md "Verifier semantics"):
- A cross-list group is one course. Its key is the smallest code of the group.
- `equivalent` and `replaces` relations make two courses interchangeable for prerequisites
  and deadlines (`alts`), but not for selectors: selectors match on cross-list groups only.
- Enrolled statuses (planned, in_progress, completed) carry quarter load and count as units
  "by enrollment" and "in residence"; transfer and exam items and `credits` do not.
- Each enrolment of a `repeatable` course is a course of its own for program requirements
  (`Taken.uid`); for everything else (prerequisites, relations, sequences) it is the one
  course `Taken.key`. A course that is not repeatable counts once, at its earliest record.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from planner_core.models import (
    AttributeValue,
    Catalog,
    Course,
    MaxFrom,
    PlanItem,
    PlanState,
    Requisite,
    RuleSet,
    Section,
    Selector,
)
from planner_core.terms import term_key, year_index

#: Units assumed for a placeholder or an unknown course without explicit units.
DEFAULT_UNITS = 100
ENROLLED = ("planned", "in_progress", "completed")

_GRADE_RANK = {
    "A+": 12.0,
    "A": 11.0,
    "A-": 10.0,
    "B+": 9.0,
    "B": 8.0,
    "B-": 7.0,
    "C+": 6.0,
    "C": 5.0,
    "C-": 4.0,
    "D+": 3.0,
    "D": 2.0,
    "P": 1.5,
    "F": 0.0,
}


def grade_ok(grade: str | None, minimum: str | None) -> bool:
    """True when `grade` meets `minimum`. A missing grade (course not graded yet) is assumed
    to meet it; an unreadable grade or minimum does not (strictest reading)."""
    if minimum is None or grade is None:
        return True
    have, need = _GRADE_RANK.get(grade.strip().upper()), _GRADE_RANK.get(minimum.strip().upper())
    return have is not None and need is not None and have >= need


class Index:
    """Catalog facts keyed for constant-time lookup."""

    def __init__(self, catalog: Catalog, rules: RuleSet) -> None:
        self.courses: dict[str, Course] = {c.code: c for c in catalog.courses}
        self._canon: dict[str, str] = {}
        self._members: dict[str, tuple[str, ...]] = {}
        for group in catalog.crosslist_groups:
            key = min(group)
            self._members[key] = tuple(sorted(group))
            for code in group:
                self._canon[code] = key
        self._lists = {cl.name: cl for cl in catalog.course_lists}
        self._list_members: dict[str, frozenset[str]] = {}
        self._matches: dict[tuple[int, str], bool] = {}
        self._selectors: list[Selector] = []  # keeps cached selector ids alive
        self._alts: dict[str, set[str]] = {}
        #: (key a, key b, kind) for every relation, in catalog order.
        self.relations: list[tuple[str, str, str]] = []
        for rel in catalog.relations:
            a, b = self.canon(rel.a), self.canon(rel.b)
            self.relations.append((a, b, rel.kind))
            if rel.kind in ("equivalent", "replaces"):
                self._alts.setdefault(a, set()).add(b)
                self._alts.setdefault(b, set()).add(a)
        self._requisites: dict[str, Requisite] = {r.course: r for r in rules.requisites}
        self._offered: dict[tuple[str, str], float] = {}
        self._has_pattern: set[str] = set()
        for o in catalog.offerings:
            key = self.canon(o.course)
            self._has_pattern.add(key)
            slot = (key, o.quarter)
            self._offered[slot] = max(self._offered.get(slot, 0.0), o.p_offered)
        #: Terms with a posted schedule (at least one section of any course).
        self.posted_terms: set[str] = set()
        self._sections: dict[tuple[str, str], list[Section]] = {}
        for s in catalog.sections:
            self.posted_terms.add(s.term)
            if (s.status or "").lower() not in ("cancelled", "canceled"):
                self._sections.setdefault((s.term, self.canon(s.course)), []).append(s)
        self._attributes: dict[tuple[str, str], AttributeValue] = {
            (self.canon(a.subject_id), a.key): a
            for a in catalog.attributes
            if a.subject_type == "course"
        }

    # ------------------------------------------------------------------ courses

    def canon(self, code: str) -> str:
        """The key of the cross-list group `code` belongs to (the code itself if none)."""
        return self._canon.get(code, code)

    def members(self, code: str) -> tuple[str, ...]:
        return self._members.get(self.canon(code), (code,))

    def course(self, code: str) -> Course | None:
        """Catalog facts for `code`, or for a cross-listed partner when `code` has no row."""
        if code in self.courses:
            return self.courses[code]
        return next((self.courses[m] for m in self.members(code) if m in self.courses), None)

    def known(self, code: str) -> bool:
        return self.course(code) is not None

    def units(self, code: str) -> int:
        course = self.course(code)
        return course.units if course is not None else DEFAULT_UNITS

    def tags(self, code: str) -> set[str]:
        """Tags of the whole cross-list group, with `core:<t>` for each core tag."""
        found: set[str] = set()
        for member in self.members(code):
            found |= _tags(self.courses.get(member))
        return found

    def alts(self, code: str) -> set[str]:
        """Keys that count as `code` for prerequisites and deadlines: its cross-list group
        plus `equivalent` and `replaces` partners."""
        key = self.canon(code)
        return {key} | self._alts.get(key, set())

    # ------------------------------------------------------------------ lists and selectors

    def list_members(self, name: str) -> frozenset[str]:
        """Keys of every course in the list, sublists included."""
        if name not in self._list_members:
            self._list_members[name] = frozenset()  # guards against sublist cycles
            found: set[str] = set()
            if (cl := self._lists.get(name)) is not None:
                found = {self.canon(c) for c in cl.courses}
                for sub in cl.sublists:
                    found |= self.list_members(sub)
            self._list_members[name] = frozenset(found)
        return self._list_members[name]

    def list_codes(self, name: str, limit: int = 6) -> list[str]:
        """A few member codes, in authoring order, for fix hints."""
        cl = self._lists.get(name)
        if cl is None:
            return []
        codes = list(cl.courses)
        for sub in cl.sublists:
            if len(codes) >= limit:
                break
            codes += [c for c in self.list_codes(sub, limit) if c not in codes]
        return codes[:limit]

    def sequences(self, selectors: list[Selector]) -> dict[str, frozenset[str]]:
        """Sequence name -> member keys: one entry per sublist of every list the selectors
        name (docs/CONTRACTS.md "Sequences")."""
        found: dict[str, frozenset[str]] = {}
        for selector in selectors:
            if selector.list_ is not None and (cl := self._lists.get(selector.list_)) is not None:
                for sub in cl.sublists:
                    found[sub] = self.list_members(sub)
            found.update(self.sequences(selector.union))
        return found

    def matches(self, selector: Selector, code: str) -> bool:
        """Selector semantics of docs/CONTRACTS.md, on cross-list groups."""
        cache_key = (id(selector), self.canon(code))
        if cache_key not in self._matches:
            self._selectors.append(selector)
            self._matches[cache_key] = self._match(selector, code)
        return self._matches[cache_key]

    def _match(self, selector: Selector, code: str) -> bool:
        key, group = self.canon(code), self.members(code)
        if any(self.canon(x) == key for x in selector.exclude):
            return False
        if selector.codes and not any(self.canon(x) == key for x in selector.codes):
            return False
        if selector.list_ is not None and key not in self.list_members(selector.list_):
            return False
        if selector.union and not any(self.matches(sub, code) for sub in selector.union):
            return False
        return any(self._member_matches(selector, member) for member in group)

    def matches_enrolled(self, selector: Selector, code: str) -> bool:
        """`matches`, and the code as written in the plan itself meets the selector's subject,
        number range and tags (cross-listed partners are not looked at). Used by `max_from`
        limits that set `as_enrolled`."""
        if not self.matches(selector, code) or not self._member_matches(selector, code):
            return False
        return not selector.union or any(self.matches_enrolled(s, code) for s in selector.union)

    def counts(self, limit: MaxFrom, code: str) -> bool:
        """Does a course taken as `code` count toward a `max_from` limit?"""
        if limit.as_enrolled:
            return self.matches_enrolled(limit.selector, code)
        return self.matches(limit.selector, code)

    def _member_matches(self, selector: Selector, code: str) -> bool:
        subject, number = code.split(" ")
        if selector.subject is not None and subject != selector.subject:
            return False
        if selector.number_range is not None:
            low, high = selector.number_range
            if not low <= int(number) <= high:
                return False
        return not selector.tags or bool(_tags(self.courses.get(code)) & set(selector.tags))

    # ------------------------------------------------------------------ other facts

    def requisite(self, code: str) -> Requisite | None:
        """The requisite of `code`, else of the first cross-listed partner that has one."""
        if code in self._requisites:
            return self._requisites[code]
        return next(
            (self._requisites[m] for m in self.members(code) if m in self._requisites), None
        )

    def p_offered(self, code: str, quarter: str) -> float | None:
        """Predicted availability; None when the course has no offering pattern at all, and
        0.0 when it has patterns but none for this quarter."""
        key = self.canon(code)
        if key not in self._has_pattern:
            return None
        return self._offered.get((key, quarter), 0.0)

    def sections(self, term: str, code: str) -> list[Section]:
        return self._sections.get((term, self.canon(code)), [])

    def attribute(self, code: str, key: str) -> AttributeValue | None:
        return self._attributes.get((self.canon(code), key))


def _tags(course: Course | None) -> set[str]:
    if course is None:
        return set()
    return set(course.tags) | {f"core:{t}" for t in course.core_tags}


def describe_selector(selector: Selector, idx: Index | None = None) -> str:
    """Plain-English form of a selector, for messages and fix hints."""
    parts: list[str] = []
    if selector.codes:
        parts.append(" or ".join(selector.codes))
    if selector.subject and selector.number_range:
        parts.append(f"{selector.subject} {selector.number_range[0]}-{selector.number_range[1]}")
    elif selector.subject:
        parts.append(f"any {selector.subject} course")
    elif selector.number_range:
        parts.append(f"courses numbered {selector.number_range[0]}-{selector.number_range[1]}")
    if selector.tags:
        parts.append("tagged " + " or ".join(selector.tags))
    if selector.list_:
        examples = idx.list_codes(selector.list_, 4) if idx is not None else []
        hint = f" (e.g. {', '.join(examples)})" if examples else ""
        parts.append(f"the list {selector.list_}{hint}")
    if selector.union:
        parts.append("(" + "; or ".join(describe_selector(s, idx) for s in selector.union) + ")")
    text = ", ".join(parts)
    if selector.exclude:
        text += f", except {', '.join(selector.exclude)}"
    return text


# --------------------------------------------------------------------------------------------
# Plan facts
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Taken:
    """One course the student has or plans: a plan item, or a credit mapped to a course."""

    code: str  # as written in the plan
    key: str  # cross-list group key
    term: str | None  # None = credited before entry
    status: str  # an ItemStatus, or "credit"
    units: int
    grading: str = "letter"
    grade: str | None = None
    #: 1 for the first record of the course; 2, 3, ... for later enrolments of a repeatable one.
    nth: int = 1

    @property
    def uid(self) -> str:
        """Identity for program requirements: the key, or `KEY#n` for the n-th enrolment."""
        return self.key if self.nth == 1 else f"{self.key}#{self.nth}"

    @property
    def enrolled(self) -> bool:
        return self.status in ENROLLED

    @property
    def order(self) -> tuple[int, int]:
        """Chronological sort key; credits sort before every term."""
        return term_key(self.term) if self.term is not None else (0, 0)

    @property
    def ref(self) -> str:
        """Witness token: `CODE@TERM` for an item, `credit:CODE` for a credit."""
        return f"{self.code}@{self.term}" if self.term is not None else f"credit:{self.code}"


class PlanFacts:
    """What the plan contains, keyed for the checks."""

    def __init__(self, plan: PlanState, idx: Index) -> None:
        self.plan = plan
        self.idx = idx
        #: Every course item, in chronological order (unknown codes included).
        self.items: list[Taken] = sorted(
            (
                Taken(
                    code=item.course,
                    key=idx.canon(item.course),
                    term=item.term,
                    status=item.status,
                    units=item.units if item.units is not None else idx.units(item.course),
                    grading=item.grading,
                    grade=item.grade,
                )
                for item in plan.items
                if item.course is not None
            ),
            key=lambda t: (t.order, t.code),
        )
        self.credits: list[Taken] = [
            Taken(code=c.maps_to, key=idx.canon(c.maps_to), term=None, status="credit", units=0)
            for c in plan.credits
            if c.maps_to is not None
        ]
        self.placeholders: list[PlanItem] = [i for i in plan.items if i.course is None]
        #: `uid` -> record, for every known course: its earliest record under its key
        #: (credits first), and later enrolments of a repeatable course under `KEY#n`.
        self.taken: dict[str, Taken] = {}
        seen: dict[str, int] = {}
        for taken in [*self.credits, *self.items]:
            course = idx.course(taken.code)
            if course is None:
                continue
            seen[taken.key] = seen.get(taken.key, 0) + 1
            if seen[taken.key] == 1:
                self.taken[taken.key] = taken
            elif course.repeatable:
                again = replace(taken, nth=seen[taken.key])
                self.taken[again.uid] = again
        #: Load-bearing course items per term (enrolled statuses only).
        self.by_term: dict[str, list[Taken]] = {}
        #: Units per term: enrolled course items plus placeholders.
        self.loads: dict[str, int] = {}
        for taken in self.items:
            if taken.enrolled and taken.term is not None:
                self.by_term.setdefault(taken.term, []).append(taken)
                self.loads[taken.term] = self.loads.get(taken.term, 0) + taken.units
        for item in self.placeholders:
            units = item.units if item.units is not None else DEFAULT_UNITS
            self.by_term.setdefault(item.term, [])
            self.loads[item.term] = self.loads.get(item.term, 0) + units
        self.terms: list[str] = sorted(self.loads, key=term_key)

    def course_count(self, term: str) -> int:
        """Courses carried in `term`, placeholders included."""
        return len(self.by_term.get(term, [])) + sum(p.term == term for p in self.placeholders)

    def class_year(self, term: str) -> int:
        """Class standing in `term`: 1 = first-year (entry level 2 for most transfers)."""
        return year_index(term, self.plan.entry_term) + self.plan.entry_year_level - 1

    def done(self, code: str, by: str | None = None, *, strict: bool = False) -> Taken | None:
        """The earliest record of `code` (or an alternative), optionally on or before term
        `by` (strictly before when `strict`)."""
        hits = [self.taken[k] for k in sorted(self.idx.alts(code)) if k in self.taken]
        if by is not None:
            limit = term_key(by)
            hits = [t for t in hits if t.order < limit or (not strict and t.order == limit)]
        return min(hits, key=lambda t: (t.order, t.code), default=None)
