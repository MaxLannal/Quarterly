"""Deterministic plan generator (SPEC "A1. Plan generator", steps 1, 2, 4, 5 and 7, without
an LLM). Pure: Pydantic in, Pydantic out; the solver runs single-threaded.

1. **Load.** The plan's fixed courses (completed, in progress, credited, locked, or outside
   the quarters being planned) stay where they are. Unlocked planned courses in those
   quarters, and a pool of catalog courses, *float*: the solver decides whether and where they
   go. The pool holds the courses that can fill the plan's requirements (the best few per
   requirement by preference, whole sequences for sequence lists), the courses a goal names,
   their prerequisites, and free electives.
2. **Compile goals** (`goalcompile`): hard bounds, rewards and penalties.
3. **Preferences**: from the agent when given, else the default ranking (`preferences`).
4. **Solve** (CP-SAT): `place[c, t]` for each floating course c and open quarter t, at most
   one quarter per course; prerequisites by earlier quarters (co-requisites by the same or an
   earlier one); `p_offered` >= 0.3 unless the student accepts a rarely offered course; full
   time loads, the 500-unit overload only where the plan claims a reason that applies; locked
   and completed courses fixed; program satisfaction through the V07 model
   (`solver.ProgramModel`), with sharing limits and residency; graduation totals.
   Objective: preferences + goal rewards - penalties (including workload spikes) - a cost per
   course, so only the courses a requirement, a goal or a full-time load needs are added.
   Up to three variants, each differing from every earlier one in at least 4 placements.
5. **Verify**: every variant goes through `verify` and `check_certificate`; a variant they
   reject is dropped and reported in `alerts` (it would be a bug in this module).
6. **Infeasible requests**: every hard goal and limit is an assumption literal; the smallest
   set of them that cannot hold together is named in plain English.
7. **Return** each variant as change operations against the current plan.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from fractions import Fraction
from itertools import pairwise
from typing import Any

from ortools.sat.python import cp_model

from planner_core.checks import P_OFFERED_WARN, reason_applies
from planner_core.dsl import expr_courses, residency_fraction, share_applies
from planner_core.goalcompile import GoalSpec, compile_goals, term_label
from planner_core.index import ENROLLED, Index, PlanFacts, Taken, grade_ok
from planner_core.models import (
    STANDINGS,
    AddOp,
    Atom,
    Catalog,
    ChangeOp,
    Conflict,
    Expr,
    GenerateOptions,
    GenerateResult,
    Infeasibility,
    MoveOp,
    PlanItem,
    PlanState,
    RemoveOp,
    RuleSet,
    Variant,
)
from planner_core.preferences import MAX_PREFERENCE, interest_match, preferences
from planner_core.prereqs import placement_values
from planner_core.programs import plan_programs
from planner_core.solver import ProgramModel
from planner_core.terms import parse_term, resolve_term_ref, term_at, term_key
from planner_core.tree import Compiled, compile_program
from planner_core.verify import verify_checked

#: Cost of one added course: above every preference, so preferences only choose *which*
#: courses fill what is needed, never add courses for their own sake.
COURSE_COST = MAX_PREFERENCE + 1
#: An unlocked course the student placed keeps its quarter / stays in the plan.
KEEP_TERM = 2000
KEEP_PLAN = MAX_PREFERENCE + 1  # keeping the student's own course costs nothing
#: Pool sizes.
POOL_SPARE = 6
SEQUENCES_KEPT = 4
FREE_ELECTIVES = 40
PREREQ_DEPTH = 3
MAX_POOL = 450
#: Preference taken off courses that need the instructor's consent.
CONSENT_PENALTY = 5000
#: Penalty per Core course placed after the College's Core deadline (V10 warns about it).
LATE_CORE = 3000
#: Hours and difficulty are compared in tenths.
SCALE = 10
#: Explaining an impossible request: solver budget per check (share of `time_limit_s`), and
#: the most checks used to shrink the set of conflicting goals.
EXPLAIN_SHARE = 0.1
EXPLAIN_STEPS = 6
#: Plans with this many programs go straight to the staged solve.
STAGED_PROGRAMS = 4
#: Seconds kept back from the time limit for building and verifying the variants.
RESERVE_S = 0.3
#: The least time the second step of the staged solve gets, and the least worth spending on
#: improving a plan or finding another variant.
STAGE2_MIN_S = 0.5
MIN_SOLVE_S = 0.2
#: The shortest solve worth running while explaining an impossible request.
EXPLAIN_MIN_S = 0.05
#: Parallel search workers per solve.
SEARCH_WORKERS = 8
#: Scale of goal rewards and penalties relative to preferences.
GOAL_SCALE = 200
#: Most course items a plan may hold, and how far its quarters may lie from its entry year.
MAX_ITEMS = 200
MAX_YEARS = 8
#: Placements a variant must change relative to every earlier one.
MIN_DIFFERENCE = 4
#: Floating courses are compiled into the program model under this term; their real term is
#: decided by `place`.
FLOAT_TERM = "9999-AU"
_STATUS_OK = (cp_model.OPTIMAL, cp_model.FEASIBLE)


def horizon(plan: PlanState) -> list[str]:
    """The plan's quarters: Autumn, Winter and Spring of each remaining year (four years for a
    first-year, fewer for a transfer), plus every quarter that already has an item."""
    years = max(1, 5 - plan.entry_year_level)
    terms = {
        term_at(plan.entry_term, y, q) for y in range(1, years + 1) for q in ("AU", "WI", "SP")
    }
    terms = {t for t in terms if term_key(t) >= term_key(plan.entry_term)}
    terms |= {item.term for item in plan.items}
    return sorted(terms, key=term_key)


def open_terms(plan: PlanState, options: GenerateOptions) -> list[str]:
    """Quarters the generator may change: never Summer, never before `today_term`, and only the
    selected ones for scope "selected"."""
    terms = [t for t in horizon(plan) if parse_term(t)[1] != "SU"]
    if options.today_term is not None:
        terms = [t for t in terms if term_key(t) >= term_key(options.today_term)]
    if options.scope == "selected":
        chosen = set(options.selected_terms)
        terms = [t for t in terms if t in chosen]
    return terms


@dataclass
class _Floating:
    uid: str
    code: str
    units: int
    item: PlanItem | None = None  # the student's own unlocked course, if it is one
    place: dict[str, Any] = field(default_factory=dict)  # term -> bool var
    used: Any = None


class _Builder:
    def __init__(
        self, plan: PlanState, rules: RuleSet, catalog: Catalog, options: GenerateOptions
    ) -> None:
        self.plan, self.rules, self.catalog, self.options = plan, rules, catalog, options
        #: Every solve ends before this `time.monotonic()` value (set by `generate`).
        self.deadline = float("inf")
        self.idx = Index(catalog, rules)
        self.college = rules.college
        self.terms = horizon(plan)
        self.open = open_terms(plan, options)
        self.open_set = set(self.open)
        self.ordinal = {t: i for i, t in enumerate(self.terms)}
        self.assumptions: list[str] = []
        self.conflicts: dict[int, Conflict] = {}  # literal index -> what it stands for
        self.conflicts_by_id: dict[str, Conflict] = {}
        self.literals: list[Any] = []

        fixed_items: list[PlanItem] = []
        self.floating_items: list[PlanItem] = []
        self.dropped: list[PlanItem] = []  # requirement placeholders in open quarters
        for item in plan.items:
            in_open = item.term in self.open_set
            if item.course is None:
                (self.dropped if in_open else fixed_items).append(item)
            elif item.status == "planned" and not item.locked and in_open:
                self.floating_items.append(item)
            else:
                fixed_items.append(item)
        self.fixed_plan = plan.model_copy(update={"items": fixed_items})
        self.fixed = PlanFacts(self.fixed_plan, self.idx)
        self.specs = compile_goals(
            list(options.goals if options.goals is not None else plan.goals), plan, rules, self.idx
        )

    # ------------------------------------------------------------------ pool

    def pool(self, programs: list[Compiled]) -> dict[str, int]:
        """Catalog courses worth considering, with their preference."""
        idx, fixed_keys = self.idx, set(self.fixed.taken)
        codes = [c.code for c in self.catalog.courses]
        prefs = preferences(idx, codes, self.options.interests, self.options.preferences)
        for code in codes:  # avoid courses that need the instructor's consent when possible
            req = idx.requisite(code)
            if req is not None and any(_has_consent(e) for e in (req.prereq, req.coreq) if e):
                prefs[code] = max(0, prefs[code] - CONSENT_PENALTY)
        repeatable = {c.code for c in self.catalog.courses if c.repeatable}

        def usable(code: str) -> bool:
            return idx.known(code) and (code in repeatable or idx.canon(code) not in fixed_keys)

        def best(found: list[str], k: int) -> list[str]:
            return sorted(found, key=lambda c: (-prefs.get(c, 0), c))[:k]

        required: list[str] = [i.course for i in self.floating_items if i.course is not None]
        extra: list[str] = []
        for compiled in programs:
            for unit in compiled.units.values():
                sel = unit.selector
                if sel.codes:
                    found = [c for c in sel.codes if usable(c)]
                    required += found
                    continue
                if sel.list_ is not None and not sel.union and sel.subject is None:
                    members = idx.list_members(sel.list_)
                    found = [c for c in codes if idx.canon(c) in members and usable(c)]
                else:
                    found = [c for c in codes if usable(c) and idx.matches(sel, c)]
                sequences = idx.sequences([sel]) if sel.list_ is not None else {}
                if sequences:
                    ranked = sorted(
                        sequences.items(),
                        key=lambda kv: (-max((prefs.get(c, 0) for c in kv[1]), default=0), kv[0]),
                    )
                    for _, members in ranked[:SEQUENCES_KEPT]:
                        required += [c for c in found if idx.canon(c) in members]
                need = unit.cap or unit.need or -(-(unit.need_units or 0) // 100)
                extra += best(found, need + POOL_SPARE)
        for spec in self.specs:
            required += [c for c in spec.courses if usable(c)]
        # Prerequisites of everything so far, and of the fixed courses still to be taken.
        frontier = [*required, *extra]
        frontier += [t.code for t in self.fixed.items if t.status == "planned"]
        for _ in range(PREREQ_DEPTH):
            nxt: list[str] = []
            for code in frontier:
                req = idx.requisite(code)
                for expr in (req.prereq, req.coreq, req.restrictions) if req else ():
                    if expr is not None:
                        nxt += [c for c in sorted(expr_courses(expr)) if usable(c)]
            required += nxt
            frontier = nxt
        electives = [
            c for c in codes if usable(c) and int(c.split(" ")[1]) < 30000 and self._free(c)
        ]
        chosen: dict[str, int] = {}
        keys: set[str] = set()
        for code in [*required, *extra, *best(electives, FREE_ELECTIVES)]:
            key = idx.canon(code)
            if key not in keys:
                keys.add(key)
                chosen[code] = prefs.get(code, 0)
            if len(chosen) >= MAX_POOL:
                break
        return chosen

    def _free(self, code: str) -> bool:
        """No course prerequisite, no restriction, offered in some regular quarter."""
        req = self.idx.requisite(code)
        if req is not None and (req.restrictions is not None or req.prereq is not None):
            return False
        offered = [self.idx.p_offered(code, q) for q in ("AU", "WI", "SP")]
        return any(p is None or p >= P_OFFERED_WARN for p in offered)

    # ------------------------------------------------------------------ model

    def literal(self, conflict: Conflict) -> Any:
        lit = self.m.new_bool_var(conflict.id)
        self.conflicts[lit.index] = conflict
        self.conflicts_by_id[conflict.id] = conflict
        self.literals.append(lit)
        return lit

    def never(self, lit: Any) -> None:
        """The goal behind `lit` cannot hold."""
        self.m.add_bool_or([lit.Not()])

    def build(self) -> GenerateResult | None:
        plan, idx = self.plan, self.idx
        listed = [p.program_id for p in plan.programs]
        programs = plan_programs(plan, self.rules)
        missing = sorted(set(listed) - {p.id for p in programs})
        if missing:
            return _impossible(
                f"There are no rules for {', '.join(missing)} in this catalog year.",
                [Conflict(id=f"program:{p}", kind="program", label=p) for p in missing],
            )
        college = self.college
        if college is not None and college.core_program_id not in listed:
            core = college.core_program_id
            return _impossible(
                f"Add the Core ({core}) to the plan first: graduation needs it, so no full plan "
                "can be checked without it.",
                [Conflict(id=f"program:{core}", kind="program", label=core)],
            )
        if not self.open:
            return _impossible(
                "There are no quarters left to plan in the chosen scope.",
                [Conflict(id="scope", kind="load", label="The quarters you chose")],
            )

        # Floating courses join the plan under FLOAT_TERM so the program model sees them.
        fixed0 = [compile_program(p, self.fixed, idx) for p in programs]
        self.prefs = self.pool(fixed0)
        floats: list[PlanItem] = []
        for code in self.prefs:
            course = idx.course(code)
            copies = 2 if course is not None and course.repeatable else 1
            floats += [PlanItem(course=code, term=FLOAT_TERM) for _ in range(copies)]
        augmented = self.fixed_plan.model_copy(update={"items": [*self.fixed_plan.items, *floats]})
        self.facts = PlanFacts(augmented, idx)
        self.floating: dict[str, _Floating] = {}
        claimed: dict[str, list[PlanItem]] = {}
        for item in self.floating_items:
            assert item.course is not None
            claimed.setdefault(item.course, []).append(item)
        for taken in sorted(self.facts.taken.values(), key=lambda t: (t.code, t.nth)):
            if taken.term != FLOAT_TERM:
                continue
            mine = claimed.get(taken.code, [])
            own = mine.pop(0) if mine else None
            self.floating[taken.uid] = _Floating(taken.uid, taken.code, taken.units, own)

        self.pm = ProgramModel(self.facts, idx, college, None, floating=frozenset(self.floating))
        self.m = self.pm.model
        compiled = [compile_program(p, self.facts, idx) for p in programs]
        for c in compiled:
            self.pm.program(c)
        self.compiled = {c.program.id: c for c in compiled}
        self._placements()
        self._programs(compiled)
        self._order()
        self._prerequisites()
        self._relations()
        self._loads()
        self._goals()
        self._objective()
        return None

    def _placements(self) -> None:
        m, idx, opts = self.m, self.idx, self.options
        posted = {s.term for s in self.catalog.sections}
        lit = self.literal(
            Conflict(
                id="offering",
                kind="offering",
                label="Placing courses only in quarters they are usually offered",
            )
        )
        for f in self.floating.values():
            for t in self.open:
                if t in posted and not idx.sections(t, f.code):
                    continue  # the posted schedule does not list it
                var = m.new_bool_var("")
                p = idx.p_offered(f.code, parse_term(t)[1])
                if p is not None and p < P_OFFERED_WARN and f.code not in opts.allow_rarely_offered:
                    m.add(var == 0).only_enforce_if(lit)
                f.place[t] = var
            f.used = m.new_bool_var("")
            m.add(sum(f.place.values()) == f.used)
        # A later enrolment of a repeatable course needs the earlier one, in an earlier quarter.
        by_code: dict[str, list[_Floating]] = {}
        for f in self.floating.values():
            by_code.setdefault(f.code, []).append(f)
        for group in by_code.values():
            for a, b in pairwise(group):
                m.add(b.used <= a.used)
                m.add(self.when(a) + 1 <= self.when(b)).only_enforce_if(b.used)

    def when(self, f: _Floating) -> Any:
        return sum(self.ordinal[t] * var for t, var in f.place.items())

    def _programs(self, compiled: list[Compiled]) -> None:
        m, pm, college = self.m, self.pm, self.college
        for c in compiled:
            pid = c.program.id
            lit = self.literal(
                Conflict(id=f"program:{pid}", kind="program", label=f"Completing {pid}")
            )
            root = pm.s[pid]
            if root is None:
                self.never(lit)
            else:
                m.add(root == 1).only_enforce_if(lit)
            used = [(key, pm.y(c, key)) for key in pm.keys(c)]
            for key, y in used:
                if key in self.floating:
                    m.add(y <= self.floating[key].used)
            fraction = residency_fraction(c.program, college)
            if fraction is not None and used:
                frac = Fraction(fraction).limit_denominator(1000)
                home = sum(y for key, y in used if self.facts.taken[key].enrolled)
                total = sum(y for _, y in used)
                m.add(frac.denominator * home >= frac.numerator * total).only_enforce_if(lit)
        lit = self.literal(
            Conflict(
                id="sharing",
                kind="sharing",
                label="The limits on courses shared between your programs",
            )
        )
        for p in compiled:
            for limit in p.program.policy.share:
                for q in compiled:
                    if q is p or not share_applies(limit.with_, q.program, college):
                        continue
                    skip = tuple(limit.except_)
                    both = []
                    for key in pm.keys(p):
                        in_p, in_q = pm.y(p, key, skip), pm.y(q, key, skip)
                        if in_p is not None and in_q is not None:
                            z = m.new_bool_var("")
                            m.add(z >= in_p + in_q - 1)
                            both.append(z)
                    if len(both) > limit.max:
                        m.add(sum(both) <= limit.max).only_enforce_if(lit)

    def _order(self) -> None:
        """`in_order` between courses whose quarter the solver chooses."""
        for a, var_a, b, var_b in self.pm.order_pairs:
            if a.code.split(" ")[0] != b.code.split(" ")[0] or a.code == b.code:
                continue
            first, second = (a, b) if a.code < b.code else (b, a)
            self.m.add(self._when_taken(first) + 1 <= self._when_taken(second)).only_enforce_if(
                [var_a, var_b]
            )

    def _when_taken(self, taken: Taken) -> Any:
        if taken.uid in self.floating:
            return self.when(self.floating[taken.uid])
        if taken.term is None:
            return -1
        return self.ordinal.get(
            taken.term, -1 if term_key(taken.term) < term_key(self.terms[0]) else len(self.terms)
        )

    # -------------------------------------------------------------- prerequisites

    def holds(self, expr: Expr, term: str, *, coreq: bool, own: str) -> Any:
        """1, 0, or an expression that is >= 1 only when `expr` holds for a course in `term`."""
        if expr.atom is not None:
            return self._atom(expr.atom, term, coreq, own)
        kids = [self.holds(child, term, coreq=coreq, own=own) for child in expr.children]
        need = {"all": len(kids), "any": 1, "n_of": expr.n or 0}[expr.op]
        sure = sum(1 for k in kids if isinstance(k, int) and k >= 1)
        maybe = [self._bool(k) for k in kids if not isinstance(k, int)]
        if sure >= need:
            return 1
        if sure + len(maybe) < need:
            return 0
        if expr.op == "any":
            return sum(maybe)
        flag = self.m.new_bool_var("")
        self.m.add((need - sure) * flag <= sum(maybe))
        return flag

    def _bool(self, value: Any) -> Any:
        if isinstance(value, cp_model.IntVar):
            return value
        flag = self.m.new_bool_var("")
        self.m.add(flag <= value)
        return flag

    def _atom(self, atom: Atom, term: str, coreq: bool, own: str) -> Any:
        facts, idx = self.fixed, self.idx
        if atom.kind in ("course", "concurrent"):
            strict = atom.kind == "course" and not coreq
            limit = term_key(term)
            alts = idx.alts(atom.value) - {own}
            for key in alts:
                taken = facts.taken.get(key)
                if taken is None:
                    continue
                if (taken.order < limit or (not strict and taken.order == limit)) and grade_ok(
                    taken.grade, atom.min_grade
                ):
                    return 1
            terms = [t for t in self.open if term_key(t) < limit or (not strict and t == term)]
            vars_ = [
                f.place[t]
                for f in self.floating.values()
                if self.idx.canon(f.code) in alts
                for t in terms
                if t in f.place
            ]
            return sum(vars_) if vars_ else 0
        if atom.kind == "placement":
            return int(atom.value in placement_values(facts))
        if atom.kind == "standing":
            return int(facts.class_year(term) >= STANDINGS.index(atom.value) + 1)
        if atom.kind == "program":
            return int(any(fnmatchcase(p.program_id, atom.value) for p in self.plan.programs))
        return 1  # consent never blocks (the verifier warns)

    def _requisites(self, code: str) -> list[tuple[Expr, bool]]:
        req = self.idx.requisite(code)
        if req is None:
            return []
        found = [(req.prereq, False), (req.coreq, True), (req.restrictions, False)]
        return [(expr, coreq) for expr, coreq in found if expr is not None]

    def _prerequisites(self) -> None:
        m = self.m
        for f in self.floating.values():
            own = self.idx.canon(f.code)
            for expr, coreq in self._requisites(f.code):
                for t, var in f.place.items():
                    h = self.holds(expr, t, coreq=coreq, own=own)
                    if isinstance(h, int):
                        if h < 1:
                            m.add(var == 0)
                    else:
                        m.add(var <= h)
        lit = self.literal(
            Conflict(
                id="locked",
                kind="locked",
                label="The prerequisites of the courses you "
                "locked or already planned outside the quarters being changed",
            )
        )
        for taken in self.fixed.items:
            if taken.status != "planned" or taken.term is None or not self.idx.known(taken.code):
                continue
            for expr, coreq in self._requisites(taken.code):
                h = self.holds(expr, taken.term, coreq=coreq, own=taken.key)
                if isinstance(h, int):
                    if h < 1:
                        self.never(lit)
                else:
                    m.add(h >= 1).only_enforce_if(lit)

    def _relations(self) -> None:
        """No duplicates and no excluded pairs (V02)."""
        fixed = set(self.fixed.taken)
        by_key: dict[str, list[_Floating]] = {}
        for f in self.floating.values():
            by_key.setdefault(self.idx.canon(f.code), []).append(f)
        for rel in self.catalog.relations:
            a, b = self.idx.canon(rel.a), self.idx.canon(rel.b)
            fa, fb = by_key.get(a, []), by_key.get(b, [])
            for f in fa if b in fixed else []:
                self.m.add(f.used == 0)
            for f in fb if a in fixed else []:
                self.m.add(f.used == 0)
            if fa and fb:
                self.m.add_at_most_one([fa[0].used, fb[0].used])

    # ------------------------------------------------------------------- loads

    def count(self, term: str) -> Any:
        return self.fixed.course_count(term) + sum(
            f.place[term] for f in self.floating.values() if term in f.place
        )

    def units(self, term: str) -> Any:
        return self.fixed.loads.get(term, 0) + sum(
            f.units * f.place[term] for f in self.floating.values() if term in f.place
        )

    def _loads(self) -> None:
        m, college, opts = self.m, self.college, self.options
        self.active: dict[str, Any] = {}
        for t in self.terms:
            if parse_term(t)[1] == "SU":
                continue
            if self.fixed.course_count(t) > 0 or t not in self.open_set:
                self.active[t] = int(self.fixed.course_count(t) > 0)
                continue
            flag = m.new_bool_var("")
            vars_ = [f.place[t] for f in self.floating.values() if t in f.place]
            m.add(sum(vars_) <= len(vars_) * flag)
            m.add(sum(vars_) >= flag)
            self.active[t] = flag
        lit_load = self.literal(
            Conflict(
                id="load",
                kind="load",
                label="Keeping every quarter full time and within the College's unit limit",
            )
        )
        if college is not None:
            reasons = {r.id: r for r in college.overload_reasons}
            for t in self.terms:  # quarters outside the scope cannot be repaired here
                courses = self.fixed.by_term.get(t, [])
                if t in self.open_set or parse_term(t)[1] == "SU" or not courses:
                    continue
                load = self.fixed.loads.get(t, 0)
                history = all(x.status == "completed" for x in courses)
                low, high = college.full_time_min_units, college.full_time_max_units
                if not history and (
                    (low is not None and load < low) or (high is not None and load > high)
                ):
                    self.never(lit_load)
            for t in self.open:
                low, high = college.full_time_min_units, college.full_time_max_units
                claimed = reasons.get(self.plan.overload_reasons.get(t, ""))
                if (
                    opts.allow_overload
                    and claimed is not None
                    and college.overload_units is not None
                    and reason_applies(claimed, t, self.fixed, self.idx)
                ):
                    high = college.overload_units
                if low is not None:
                    m.add(self.units(t) >= low * self.active[t]).only_enforce_if(lit_load)
                if high is not None:
                    m.add(self.units(t) <= high).only_enforce_if(lit_load)
        if opts.max_courses_per_term is not None:
            lit = self.literal(
                Conflict(
                    id="courses_per_term",
                    kind="courses_per_term",
                    label=f"At most {opts.max_courses_per_term} courses per quarter",
                )
            )
            for t in self.open:
                m.add(self.count(t) <= opts.max_courses_per_term).only_enforce_if(lit)
        if college is None:
            return
        lit = self.literal(
            Conflict(
                id="graduation",
                kind="graduation",
                label="Reaching the units and number of quarters the College requires to graduate",
            )
        )
        added = sum(f.units * f.used for f in self.floating.values())
        total = sum(t.units for t in self.fixed.items if t.status in ENROLLED)
        total += sum(i.units or 100 for i in self.fixed.placeholders)
        other = sum(t.units for t in self.fixed.items if t.status not in ENROLLED)
        other += sum(c.units for c in self.plan.credits)
        if college.total_units is not None:
            m.add(total + other + added >= college.total_units).only_enforce_if(lit)
        if college.units_by_enrollment is not None:
            m.add(total + added >= college.units_by_enrollment).only_enforce_if(lit)
        if college.max_quarters is not None:
            m.add(sum(self.active.values()) <= college.max_quarters).only_enforce_if(lit)

    # ------------------------------------------------------------------- goals

    def attr(self, code: str, key: str, upper: bool = False) -> int:
        value = self.idx.attribute(code, key)
        if value is None:
            return 0
        number = value.ci_high if upper and value.ci_high is not None else value.value
        return round(number * SCALE)

    def per_term(self, spec: GoalSpec) -> list[str]:
        regular = [t for t in self.terms if parse_term(t)[1] != "SU"]
        return [t for t in regular if t in spec.terms] if spec.terms else regular

    def total(self, term: str, weight: Any) -> Any:
        """Sum over the courses in `term` of `weight(code)`."""
        fixed = sum(weight(t.code) for t in self.fixed.by_term.get(term, []))
        return fixed + sum(
            weight(f.code) * f.place[term] for f in self.floating.values() if term in f.place
        )

    def _goals(self) -> None:
        m = self.m
        self.rewards: list[Any] = []
        self.penalties: list[Any] = []
        missing: set[str] = set()
        for spec in self.specs:
            if spec.type in ("workload_hours", "difficulty_cap", "challenge", "protect_gpa"):
                key = {"workload_hours": "workload_hours", "protect_gpa": "grading_strictness"}
                attr = key.get(spec.type, "difficulty")
                missing |= {
                    f.code for f in self.floating.values() if not self.idx.attribute(f.code, attr)
                }
            hard = spec.mode in ("hard", "pin", "precedence")
            lit = (
                self.literal(Conflict(id=f"goal:{spec.goal_id}", kind="goal", label=spec.label))
                if hard
                else None
            )
            weight = max(1, round(spec.weight * GOAL_SCALE))
            if spec.type in ("course_load", "light_quarter"):
                for t in self.per_term(spec):
                    if spec.limit is not None:
                        m.add(self.count(t) <= int(spec.limit)).only_enforce_if(lit)
                    if spec.floor is not None:
                        m.add(self.count(t) >= int(spec.floor) * self.active[t]).only_enforce_if(
                            lit
                        )
            elif spec.type == "graduate_by":
                self._deadline(spec, lit)
            elif spec.type == "workload_hours":

                def hours(code: str, s: GoalSpec = spec) -> int:
                    return self.attr(code, "workload_hours", s.upper)

                limit = round((spec.limit or 0) * SCALE)
                terms = self.per_term(spec)
                if spec.aggregate == "career_average":
                    load = sum(self.total(t, hours) for t in terms)
                    bound = limit * sum(self.active[t] for t in terms)
                    self._bound(load, bound, lit, weight)
                else:
                    for t in terms:
                        self._bound(self.total(t, hours), limit, lit, weight)
            elif spec.type == "difficulty_cap":
                threshold = round((spec.threshold or 0) * SCALE)
                for t in self.per_term(spec):
                    if spec.max_very_hard is not None:

                        def very_hard(code: str, th: int = threshold) -> int:
                            return int(self.attr(code, "difficulty") >= th > 0)

                        self._bound(self.total(t, very_hard), spec.max_very_hard, lit, weight * 10)
                    if spec.limit is not None:

                        def difficulty(code: str) -> int:
                            return self.attr(code, "difficulty")

                        self._bound(
                            self.total(t, difficulty), round(spec.limit * SCALE), lit, weight
                        )
            elif spec.type == "challenge":
                self.rewards += [
                    weight * self.attr(f.code, "difficulty") * f.used
                    for f in self.floating.values()
                ]
            elif spec.type == "protect_gpa":
                threshold = round((spec.threshold or 0) * SCALE)
                for t in self.per_term(spec):

                    def strict(code: str, th: int = threshold) -> int:
                        return int(self.attr(code, "grading_strictness") >= th > 0)

                    over = m.new_int_var(0, 10, "")
                    m.add(over >= self.total(t, strict) - 1)
                    self.penalties.append(500 * weight * over)
            elif spec.type == "interest":
                self.rewards += [
                    300 * weight * f.used
                    for f in self.floating.values()
                    if interest_match(self.idx, f.code, spec.tags)
                ]
            elif spec.type == "study_abroad":
                self._abroad(spec, lit)
            else:  # bxms, premed, language: precedence
                self._precedence(spec, lit)
        if missing:
            self.assumptions.append(
                "Some courses have no workload, difficulty or grading data yet; they count as 0 "
                "for the goals that use it."
            )

    def _bound(self, value: Any, limit: Any, lit: Any, weight: int) -> None:
        """value <= limit: a hard bound under `lit`, else a penalty per unit over."""
        if lit is not None:
            self.m.add(value <= limit).only_enforce_if(lit)
            return
        over = self.m.new_int_var(0, 10**6, "")
        self.m.add(over >= value - limit)
        self.penalties.append(weight * over)

    def _deadline(self, spec: GoalSpec, lit: Any) -> None:
        assert spec.deadline is not None
        limit = term_key(spec.deadline)
        for taken in self.fixed.items:
            if taken.term is not None and taken.enrolled and term_key(taken.term) > limit:
                self.never(lit)
        for item in self.fixed.placeholders:
            if term_key(item.term) > limit:
                self.never(lit)
        for f in self.floating.values():
            for t, var in f.place.items():
                if term_key(t) > limit:
                    self.m.add(var == 0).only_enforce_if(lit)

    def _abroad(self, spec: GoalSpec, lit: Any) -> None:
        block = self.compiled.get(spec.program_id or "")
        term = spec.terms[0]
        if block is None:
            self.never(lit)
            return
        keys = set(self.pm.keys(block))
        for taken in self.fixed.by_term.get(term, []):
            if taken.uid not in keys:
                self.never(lit)
            else:
                self.m.add(self.pm.y(block, taken.uid) == 1).only_enforce_if(lit)
        for f in self.floating.values():
            y = self.pm.y(block, f.uid) if f.uid in keys else 0
            here = f.place.get(term, 0)
            self.m.add(here <= y).only_enforce_if(lit)
            if f.uid in keys:
                self.m.add(y <= here).only_enforce_if(lit)

    def _precedence(self, spec: GoalSpec, lit: Any) -> None:
        assert spec.deadline is not None
        limit = term_key(spec.deadline)

        def in_time(key: tuple[int, int]) -> bool:
            return key < limit or (not spec.strict_deadline and key == limit)

        for code in spec.courses:
            alts = self.idx.alts(code)
            if any(in_time(self.fixed.taken[k].order) for k in alts if k in self.fixed.taken):
                continue
            vars_ = [
                var
                for f in self.floating.values()
                if self.idx.canon(f.code) in alts
                for t, var in f.place.items()
                if in_time(term_key(t))
            ]
            if not vars_:
                self.never(lit)
            else:
                self.m.add(sum(vars_) >= 1).only_enforce_if(lit)

    # --------------------------------------------------------------- objective

    def _objective(self) -> None:
        m, opts = self.m, self.options
        terms = list(self.open)
        terms_term = {t: i for i, t in enumerate(terms)}
        parts: list[Any] = []
        for f in self.floating.values():
            parts.append((self.prefs.get(f.code, 0) - COURSE_COST) * f.used)
            if f.item is not None:
                parts.append(KEEP_PLAN * f.used)
                if f.item.term in f.place:
                    parts.append(KEEP_TERM * f.place[f.item.term])
        for t in terms:
            shift = opts.per_term_load.get(t, 0.0) + (opts.load if opts.load < 0 else 0.0)
            if shift < 0:
                over = m.new_int_var(0, 6, "")
                m.add(over >= self.count(t) - 3)
                parts.append(-round(8000 * -shift) * over)
            elif shift > 0:
                parts.append(round(6000 * shift) * self.count(t))
        if opts.load > 0:  # heavier: finish sooner
            for f in self.floating.values():
                parts += [
                    round(2000 * opts.load) * (len(terms) - terms_term[t]) * var
                    for t, var in f.place.items()
                ]
        college = self.college
        core = self.compiled.get(college.core_program_id) if college is not None else None
        if core is not None and college is not None and college.core_complete_by is not None:
            deadline = term_key(resolve_term_ref(college.core_complete_by, self.plan.entry_term))
            core_keys = set(self.pm.keys(core))
            for f in self.floating.values():
                if f.uid in core_keys:
                    parts += [-LATE_CORE * v for t, v in f.place.items() if term_key(t) > deadline]
        if any(self.idx.attribute(f.code, "workload_hours") for f in self.floating.values()):
            peak = m.new_int_var(0, 10**5, "")
            for t in terms:
                m.add(peak >= self.total(t, lambda code: self.attr(code, "workload_hours")))
            parts.append(-100 * peak)
        self.objective = sum(parts) + sum(self.rewards) - sum(self.penalties)
        m.maximize(self.objective)

    # ------------------------------------------------------------------- solving

    def solve(
        self, assume: list[Any], *, optimize: bool = True, budget: float | None = None
    ) -> tuple[Any, cp_model.CpSolver]:
        """Solve with the `assume` literals held true. CP-SAT searches with a single worker
        whenever a model has assumptions, and that one search is slow and luck-dependent on
        large programs (CS + Math + Bx/MS: 0.2-0.9 s with 8 workers, 1.7 s to over 4 s with
        one). So the literals are fixed as constraints on a copy of the model and every worker
        searches; `core` re-solves with assumptions when the reason for "impossible" is needed.
        The result is verified either way, so run-to-run differences are harmless."""
        m = self.m
        m.clear_assumptions()
        if optimize:
            m.maximize(self.objective)
        else:
            m.clear_objective()  # type: ignore[no-untyped-call]
        fixed = m.clone()
        if assume:
            fixed.add_bool_and(assume)
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = SEARCH_WORKERS
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = budget or self.options.time_limit_s / 2
        status = solver.solve(fixed)
        return status, solver

    def core(self, assume: list[Any], budget: float) -> list[Any]:
        """Literals of `assume` that together are impossible (all of them when CP-SAT cannot
        say within `budget`)."""
        m = self.m
        m.clear_assumptions()
        m.add_assumptions(assume)
        m.clear_objective()  # type: ignore[no-untyped-call]
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = 0
        solver.parameters.max_time_in_seconds = budget
        status = solver.solve(m)
        m.clear_assumptions()
        if status != cp_model.INFEASIBLE:
            return list(assume)
        found = set(solver.sufficient_assumptions_for_infeasibility())
        return [lit for lit in assume if lit.index in found] or list(assume)

    def staged(self, deadline: float) -> tuple[Any, cp_model.CpSolver]:
        """For hard instances: place what the programs and goals need without the graduation
        totals, then keep those placements and add only the electives the totals still need.
        The first step may use all the time left except what the second step needs."""
        grad = [lit for lit in self.literals if self.conflicts[lit.index].id == "graduation"]
        rest = [lit for lit in self.literals if lit not in grad]
        first = max(MIN_SOLVE_S, _left(deadline) - STAGE2_MIN_S)
        status, solver = self.solve(rest, optimize=False, budget=first)
        if status not in _STATUS_OK:
            return status, solver
        kept = [
            var
            for f in self.floating.values()
            for var in f.place.values()
            if solver.boolean_value(var)
        ]
        self.hint(solver)
        second = max(MIN_SOLVE_S, _left(deadline))
        status, solver = self.solve([*self.literals, *kept], optimize=False, budget=second)
        if status == cp_model.INFEASIBLE:
            # Only the first step's placements are impossible to finish, not the request: try
            # the request itself with the time left (its own INFEASIBLE is a real proof).
            return self.solve(
                self.literals, optimize=False, budget=max(MIN_SOLVE_S, _left(deadline))
            )
        return status, solver

    def hint(self, solver: cp_model.CpSolver) -> None:
        """Start the next solve from this solution."""
        self.m.clear_hints()  # type: ignore[no-untyped-call]
        for f in self.floating.values():
            for var in f.place.values():
                self.m.add_hint(var, solver.boolean_value(var))

    def capacity(self) -> Infeasibility | None:
        """An exact check before solving: can the quarters left hold the units still needed to
        graduate, under the per-quarter unit and course limits? It names the limits that make
        the difference (each one, removed alone, would leave enough room)."""
        college = self.college
        if college is None:
            return None
        enrolled = sum(t.units for t in self.fixed.items if t.status in ENROLLED)
        enrolled += sum(i.units or 100 for i in self.fixed.placeholders)
        other = sum(t.units for t in self.fixed.items if t.status not in ENROLLED)
        other += sum(c.units for c in self.plan.credits)
        needs = []
        if college.total_units is not None:
            needs.append(college.total_units - enrolled - other)
        if college.units_by_enrollment is not None:
            needs.append(college.units_by_enrollment - enrolled)
        need = max(needs, default=0)
        if need <= 0:
            return None
        sizes = sorted((f.units for f in self.floating.values()), reverse=True)
        caps: dict[str, tuple[Conflict, Any]] = {}
        load_label = "Staying within the College's unit limit each quarter"
        caps["load"] = (Conflict(id="load", kind="load", label=load_label), None)
        if self.options.max_courses_per_term is not None:
            caps["courses_per_term"] = (
                self.conflicts_by_id["courses_per_term"],
                self.options.max_courses_per_term,
            )
        for spec in self.specs:
            if spec.type in ("course_load", "light_quarter", "graduate_by"):
                caps[f"goal:{spec.goal_id}"] = (self.conflicts_by_id[f"goal:{spec.goal_id}"], spec)

        def room(skip: str | None) -> int:
            units_cap = 0
            slots = 0
            unlimited_slots = False
            for t in self.open:
                high = college.full_time_max_units if skip != "load" else None
                if high is None:
                    high = 10**6
                courses: int | None = None
                for key, (_, how) in caps.items():
                    if key == skip or key == "load":
                        continue
                    if key == "courses_per_term":
                        courses = min(courses or how, how)
                    elif how.type == "graduate_by" and how.deadline is not None:
                        if term_key(t) > term_key(how.deadline):
                            courses = 0
                    elif how.limit is not None and (not how.terms or t in how.terms):
                        courses = min(
                            courses if courses is not None else int(how.limit), int(how.limit)
                        )
                free = max(0, high - self.fixed.loads.get(t, 0))
                if courses is None:
                    unlimited_slots = True
                    units_cap += free
                else:
                    n = max(0, courses - self.fixed.course_count(t))
                    slots += n
                    units_cap += min(free, n * (sizes[0] if sizes else 0))
            if not unlimited_slots:
                units_cap = min(units_cap, sum(sizes[:slots]))
            return units_cap

        have = room(None)
        if have >= need:
            return None
        binding = [key for key in caps if room(key) >= need] or list(caps)
        conflicts = [self.conflicts_by_id["graduation"], *(caps[k][0] for k in binding)]
        deadline = next(
            (
                caps[k][1]
                for k in binding
                if k.startswith("goal:") and caps[k][1].type == "graduate_by"
            ),
            None,
        )
        if deadline is not None and deadline.deadline is not None:
            short = -(-(need - have) // 100)
            message = (
                f"Graduating by {term_label(deadline.deadline)} needs {short} more courses than "
                "your remaining quarters allow."
            )
        else:
            labels = "; ".join(caps[k][0].label.lower() for k in binding)
            at_college = (
                college.units_by_enrollment is not None
                and college.units_by_enrollment - enrolled == need
            )
            what = "units taken at the College" if at_college else "units"
            message = (
                f"To graduate you still need {need} more {what}, but the quarters left can hold "
                f"at most {have} with these limits: {labels}."
            )
        return Infeasibility(message=message, conflicts=conflicts)

    def _capped(self, budget: float) -> float:
        """`budget`, cut to the time left before the deadline."""
        return max(EXPLAIN_MIN_S, min(budget, _left(self.deadline)))

    def explain(self, core: list[Any]) -> Infeasibility:
        """Shrink an infeasible core to a minimal one and say it in plain English."""
        order = {"offering": 0, "sharing": 0, "locked": 0, "program": 1, "goal": 2}
        core = sorted(core, key=lambda lit: order.get(self.conflicts[lit.index].kind, 3))
        i, steps = 0, 0
        budget = max(0.3, self.options.time_limit_s * EXPLAIN_SHARE)
        while i < len(core) and len(core) > 1 and steps < EXPLAIN_STEPS:
            if _left(self.deadline) < EXPLAIN_MIN_S:
                break  # out of time: the core is still a correct, if larger, explanation
            steps += 1
            trial = core[:i] + core[i + 1 :]
            status, _ = self.solve(trial, optimize=False, budget=self._capped(budget))
            if status == cp_model.INFEASIBLE:
                core = trial
            else:
                i += 1
        conflicts = [self.conflicts[lit.index] for lit in core]
        message = self._message(conflicts, core)
        return Infeasibility(message=message, conflicts=conflicts)

    def _message(self, conflicts: list[Conflict], core: list[Any]) -> str:
        graduate = next(
            (
                s
                for s in self.specs
                if s.type == "graduate_by" and f"goal:{s.goal_id}" in {c.id for c in conflicts}
            ),
            None,
        )
        if graduate is not None and graduate.deadline is not None:
            shortfall = self._shortfall(graduate, core)
            if shortfall is not None and shortfall > 0:
                return (
                    f"Graduating by {term_label(graduate.deadline)} needs {shortfall} more "
                    "courses than your remaining quarters allow."
                )
        programs = [c.id.split(":", 1)[1] for c in conflicts if c.kind == "program"]
        if programs:
            detail = self._unmet(programs, core)
            if detail:
                return detail
        labels = [c.label for c in conflicts]
        if not labels:
            return "No plan meets this request within the time limit; try fewer quarters."
        if len(labels) == 1:
            return f"This can't be done with your plan: {labels[0]}."
        return (
            "These can't all be done together: "
            + "; ".join(labels)
            + ". Change or drop one of them."
        )

    def _unmet(self, programs: list[str], core: list[Any]) -> str | None:
        """Name the requirements that stay unmet when the programs are not forced."""
        relaxed = [
            lit
            for lit in core
            if self.conflicts[lit.index].id not in {f"program:{p}" for p in programs}
        ]
        m = self.m
        m.clear_assumptions()
        m.add_assumptions(relaxed)
        m.maximize(sum(self.pm.objective))
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = self._capped(
            self.options.time_limit_s * 2 * EXPLAIN_SHARE
        )
        if solver.solve(m) not in _STATUS_OK:
            return None
        missing: list[str] = []
        needs_placement = False
        for pid in programs:
            compiled = self.compiled.get(pid)
            if compiled is None:
                continue
            for path, unit in compiled.units.items():
                var = self.pm.s.get(path)
                if var is not None and solver.boolean_value(var):
                    continue
                if any(
                    self.pm.s.get(p) is not None and solver.boolean_value(self.pm.s[p])
                    for p in _ancestors(path)
                ):
                    continue  # an n_of group above it is met by another option
                examples = ", ".join(t.code for t in unit.eligible[:3])
                name = unit.label or path.rsplit("/", 1)[-1]
                missing.append(f"{name} ({examples})" if examples else name)
                for taken in unit.eligible:
                    req = self.idx.requisite(taken.code)
                    exprs = [e for e in (req.prereq, req.coreq) if e] if req else []
                    needs_placement |= any(_has_atom(e, "placement") for e in exprs)
        if not missing:
            return None
        text = (
            f"Completing {', '.join(programs)} isn't possible in the quarters available. Still "
            f"missing: {'; '.join(missing[:3])}."
        )
        if needs_placement and not self.plan.placements:
            text += " Some of these courses need a placement result; add yours to the plan."
        return text

    def _shortfall(self, spec: GoalSpec, core: list[Any]) -> int | None:
        """Courses still needed beyond what fits by the deadline."""
        assert spec.deadline is not None
        others = [
            lit for lit in self.literals if self.conflicts[lit.index].id != f"goal:{spec.goal_id}"
        ]
        others = [lit for lit in others if self.conflicts[lit.index].kind != "goal"]
        m = self.m
        m.clear_assumptions()
        m.add_assumptions(others)
        m.minimize(sum(f.used for f in self.floating.values()))
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = self._capped(
            self.options.time_limit_s * 2 * EXPLAIN_SHARE
        )
        status = solver.solve(m)
        if status not in _STATUS_OK:
            return None
        needed = round(solver.best_objective_bound)
        per_term = self.options.max_courses_per_term or self._max_courses()
        room = sum(
            max(0, per_term - self.fixed.course_count(t))
            for t in self.open
            if term_key(t) <= term_key(spec.deadline)
        )
        return needed - room

    def _max_courses(self) -> int:
        high = self.college.full_time_max_units if self.college is not None else None
        return (high or 400) // 100


def _has_atom(expr: Expr, kind: str) -> bool:
    if expr.atom is not None:
        return expr.atom.kind == kind
    return any(_has_atom(child, kind) for child in expr.children)


def _has_consent(expr: Expr) -> bool:
    return _has_atom(expr, "consent")


def _ancestors(path: str) -> list[str]:
    parts = path.split("/")
    return ["/".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]


def _impossible(message: str, conflicts: list[Conflict]) -> GenerateResult:
    return GenerateResult(infeasible=Infeasibility(message=message, conflicts=conflicts))


def _item_target(item: PlanItem) -> dict[str, Any]:
    if item.id is not None:
        return {"item_id": item.id}
    if item.course is not None:
        return {"course": item.course, "term": item.term}
    return {"slot_ref": item.slot_ref, "term": item.term}


def _variant_plan(
    b: _Builder, solver: cp_model.CpSolver, goals_plan: PlanState
) -> tuple[PlanState, list[ChangeOp], dict[str, str]]:
    placed: dict[str, str] = {}
    for f in b.floating.values():
        for t, var in f.place.items():
            if solver.boolean_value(var):
                placed[f.uid] = t
    removes: list[ChangeOp] = []
    moves: list[ChangeOp] = []
    adds: list[ChangeOp] = []
    kept: dict[int, str] = {}  # id(original item) -> new term
    for f in b.floating.values():
        if f.item is None:
            continue
        if f.uid in placed:
            kept[id(f.item)] = placed[f.uid]
            if placed[f.uid] != f.item.term:
                target = _item_target(f.item)
                target.pop("term", None)
                moves.append(MoveOp(**target, from_term=f.item.term, to_term=placed[f.uid]))
    items: list[PlanItem] = []
    for item in b.plan.items:
        if any(item is f.item for f in b.floating.values()) and id(item) in kept:
            items.append(item.model_copy(update={"term": kept[id(item)]}))
        elif any(item is f for f in [*b.floating_items, *b.dropped]):
            removes.append(RemoveOp(**_item_target(item)))
        else:
            items.append(item)
    new = sorted(
        ((t, f.code) for uid, t in placed.items() for f in [b.floating[uid]] if f.item is None),
        key=lambda pair: (term_key(pair[0]), pair[1]),
    )
    for term, code in new:
        items.append(PlanItem(course=code, term=term))
        adds.append(AddOp(course=code, term=term))
    plan = goals_plan.model_copy(update={"items": items})
    return plan, [*removes, *moves, *adds], placed


def _metrics(b: _Builder, plan: PlanState, ops: list[ChangeOp]) -> dict[str, float]:
    facts = PlanFacts(plan, b.idx)
    regular = [t for t in facts.terms if parse_term(t)[1] != "SU" and facts.by_term.get(t)]
    units = [facts.loads[t] for t in regular]
    hours = []
    for t in regular:
        values = [b.idx.attribute(x.code, "workload_hours") for x in facts.by_term[t]]
        hours.append(sum(v.value for v in values if v is not None))
    return {
        "courses_added": float(sum(isinstance(op, AddOp) for op in ops)),
        "courses_moved": float(sum(isinstance(op, MoveOp) for op in ops)),
        "courses_removed": float(sum(isinstance(op, RemoveOp) for op in ops)),
        "quarters": float(len(regular)),
        "avg_units": round(sum(units) / len(units), 1) if units else 0.0,
        "max_units": float(max(units, default=0)),
        "avg_hours": round(sum(hours) / len(hours), 1) if hours else 0.0,
        "hardest_quarter_hours": round(max(hours, default=0.0), 1),
    }


def generate(
    plan: PlanState, rules: RuleSet, catalog: Catalog, options: GenerateOptions | None = None
) -> GenerateResult:
    """Generate up to `options.variants` verified plans, or explain why none exists."""
    options = options or GenerateOptions()
    # Every solve below fits before this deadline (less RESERVE_S for verifying the variants):
    # finding a first plan may use all of it; improving it and further variants get what is left.
    deadline = time.monotonic() + options.time_limit_s
    entry_year = parse_term(plan.entry_term)[0]
    far = [i.term for i in plan.items if abs(parse_term(i.term)[0] - entry_year) > MAX_YEARS]
    if len(plan.items) > MAX_ITEMS or far:
        return _impossible(
            f"This plan is too large to generate for (at most {MAX_ITEMS} courses, within "
            f"{MAX_YEARS} years of the entry quarter).",
            [],
        )
    b = _Builder(plan, rules, catalog, options)
    b.deadline = deadline
    early = b.build()
    if early is not None:
        return early
    goals_plan = plan.model_copy(
        update={"goals": options.goals if options.goals is not None else plan.goals}
    )
    short = b.capacity()
    if short is not None:
        return GenerateResult(infeasible=short)
    budget = options.time_limit_s
    # Find any plan first (fast without an objective), then improve it from that start.
    if len(b.compiled) >= STAGED_PROGRAMS:
        # Many programs at once (e.g. CS + Math + Bx/MS + Core): the direct search rarely
        # finds a plan in time, the staged one does.
        status, solver = b.staged(deadline)
    else:
        status, solver = b.solve(b.literals, optimize=False, budget=budget * 0.15)
        if status not in _STATUS_OK and status != cp_model.INFEASIBLE:
            status, solver = b.staged(deadline)
    polish = min(budget * 0.1, _left(deadline))
    if status in _STATUS_OK and polish >= MIN_SOLVE_S:
        b.hint(solver)
        better, polished = b.solve(b.literals, budget=polish)
        if better in _STATUS_OK:
            status, solver = better, polished
    rest = budget * 0.15 / max(1, options.variants - 1)
    if status == cp_model.INFEASIBLE:
        # The core decides which limits the explanation names: it may use all the time left
        # (usually well under 0.2 s; much longer only on a busy machine).
        core = b.core(list(b.literals), b._capped(budget))
        return GenerateResult(infeasible=b.explain(core))
    if status not in _STATUS_OK:
        return _impossible(
            "No plan was found within the time limit. Try a smaller scope or fewer goals.", []
        )
    result = GenerateResult()
    earlier: list[dict[str, str]] = []
    for n in range(options.variants):
        if n > 0:
            if _left(deadline) < MIN_SOLVE_S:
                break
            b.hint(solver)
            status, solver = b.solve(b.literals, budget=min(rest, _left(deadline)))
            if status not in _STATUS_OK:
                break
        vplan, ops, placed = _variant_plan(b, solver, goals_plan)
        earlier.append(placed)
        _differ(b, placed)
        label = f"Option {'ABC'[n]}"
        report, problems = verify_checked(vplan, rules, catalog)
        if problems or report.certificate is None or report.status == "errors":
            codes = sorted({i.code for i in report.issues if i.level == "error"})
            result.alerts.append(
                f"ALERT {label} was dropped: verify/check_certificate rejected it "
                f"(errors {codes}, checker problems {problems[:3]})."
            )
            continue
        report = report.model_copy(update={"assumptions": [*report.assumptions, *b.assumptions]})
        result.variants.append(
            Variant(
                label=label, plan=vplan, ops=ops, report=report, metrics=_metrics(b, vplan, ops)
            )
        )
    if not result.variants and result.alerts:
        result.infeasible = Infeasibility(
            message="The generator found plans, but none passed verification. This is a bug; it "
            "has been reported.",
        )
    return result


def _left(deadline: float) -> float:
    """Seconds a solve may still take before `deadline`, keeping RESERVE_S back."""
    return deadline - time.monotonic() - RESERVE_S


def _differ(b: _Builder, placed: dict[str, str]) -> None:
    """Later variants change at least MIN_DIFFERENCE placements of this one."""
    same = [b.floating[uid].place[t] for uid, t in placed.items()]
    others = [
        var for f in b.floating.values() for t, var in f.place.items() if placed.get(f.uid) != t
    ]
    b.m.add(len(same) - sum(same) + sum(others) >= MIN_DIFFERENCE)
