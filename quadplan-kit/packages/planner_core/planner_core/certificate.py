"""The trusted certificate checker (SPEC "Certificates and the trusted checker").

Small and boring on purpose: no solver import, one pass over the plan, the rule trees and the
certificate. A plan may be shown as "Valid" only if `check_certificate` returns True.

A certificate is accepted when all of this holds:
 1. `plan_hash` is the hash of this plan, and `rules` lists exactly the plan's programs with
    the hashes of the rules given here.
 2. Every assigned course is in the plan, matches the selector of its unit (slot, select or
    bounded_parts part), is letter-graded and meets the grade minimum where the rules ask.
 3. Within a program a course fills one unit only, unless the rule allows double counting.
 4. With these assignments every program's root node is satisfied: counts, units, part
    bounds and totals, group `all` / `n_of`, and the set constraints of every node.
 5. Every share limit between two of the plan's programs holds.
 6. Every planned or in-progress course that has a requisite has a witness; each witness
    cites only facts of the plan, and the cited facts alone make the expression true.
 7. `loads` and `goals` equal the values recomputed from the plan, and no hard goal fails.

It does not re-check V01, V02, V04-V06, V09 or V10: those are plain lookups in the report.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

from planner_core.dsl import AnyNode, excepted, share_applies
from planner_core.goals import ProgramState, evaluate_goals
from planner_core.hashing import plan_hash, program_key, rules_hash
from planner_core.index import DEFAULT_UNITS, ENROLLED, Index, PlanFacts, Taken, grade_ok
from planner_core.models import (
    STANDINGS,
    Catalog,
    Certificate,
    Constraints,
    Expr,
    GroupNode,
    PlanState,
    ProgramRules,
    RuleSet,
    SelectNode,
    Selector,
    SlotNode,
)
from planner_core.tree import out_of_order, stricter

#: Course key -> the plan's records of that course (credits and items).
Records = dict[str, list[Taken]]


def check_certificate(
    plan: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    certificate: Certificate,
) -> bool:
    """True only if every claim in `certificate` holds for `plan` under `rules` (SPEC
    "Certificates and the trusted checker"). `catalog` supplies course facts for selectors."""
    try:
        return not certificate_problems(plan, rules, catalog, certificate)
    except Exception:  # a malformed certificate is a rejected certificate
        return False


def certificate_problems(
    plan: PlanState, rules: RuleSet, catalog: Catalog, cert: Certificate
) -> list[str]:
    """Why the certificate is rejected; empty when it is accepted."""
    idx = Index(catalog, rules)
    facts = PlanFacts(plan, idx)
    bad: list[str] = []

    # 1. The certificate is about this plan and these rules.
    if cert.plan_hash != plan_hash(plan):
        bad.append("plan_hash does not match the plan")
    by_id = {p.id: p for p in rules.programs}
    listed = list(dict.fromkeys(p.program_id for p in plan.programs))
    bad += [f"no rules for program {pid}" for pid in listed if pid not in by_id]
    programs = [by_id[pid] for pid in listed if pid in by_id]
    if cert.rules != {program_key(p): rules_hash(p) for p in programs}:
        bad.append("rule hashes do not match the plan's programs")

    # 2-4. Assignments and node satisfaction.
    assigned: dict[str, list[str]] = {}
    for entry in cert.assignments:
        if entry.node in assigned:
            bad.append(f"{entry.node} is assigned twice")
        assigned[entry.node] = entry.courses
    trees = {p.id: _Tree(p, assigned, facts, idx) for p in programs}
    satisfied = {pid for pid, tree in trees.items() if tree.check()}
    for pid, tree in trees.items():
        bad += tree.problems
        if pid not in satisfied:
            bad.append(f"{pid} is not satisfied by the assignments")
    seen = {path for tree in trees.values() for path in tree.units}
    bad += [f"{path} is not a unit of the plan's programs" for path in assigned if path not in seen]

    # 5. Share limits.
    for p in programs:
        for limit in p.policy.share:
            for q in programs:
                if q is not p and share_applies(limit.with_, q, rules.college):
                    both = trees[p.id].keys(limit.except_) & trees[q.id].keys(limit.except_)
                    if len(both) > limit.max:
                        bad.append(f"{p.id} shares {sorted(both)} with {q.id}; max {limit.max}")

    # 6. Prerequisite witnesses.
    witnesses = {(w.course, w.term): set(w.by) for w in cert.prereq_witnesses}
    records: Records = {}
    for t in [*facts.credits, *facts.items]:
        if idx.known(t.code):
            records.setdefault(t.key, []).append(t)
    refs = {t.ref for found in records.values() for t in found}
    for item in facts.items:
        requisite = idx.requisite(item.code)
        if item.status not in ("planned", "in_progress") or requisite is None:
            continue
        exprs = [
            (requisite.prereq, False),
            (requisite.coreq, True),
            (requisite.restrictions, False),
        ]
        if all(expr is None for expr, _ in exprs) or not idx.known(item.code):
            continue
        tokens = witnesses.get((item.code, item.term or ""))
        if tokens is None:
            bad.append(f"no prerequisite witness for {item.ref}")
            continue
        if not all(t in refs or _is_fact(t, item, facts) for t in tokens):
            bad.append(f"the witness for {item.ref} cites something that is not in the plan")
        for expr, coreq in exprs:
            if expr is not None and not _holds(expr, item, tokens, records, idx, coreq):
                bad.append(f"the witness for {item.ref} does not satisfy its requisite")

    # 7. Loads and goals recompute to the same values.
    loads: dict[str, int] = {}
    for it in plan.items:
        if it.course is None or it.status in ENROLLED:
            default = idx.units(it.course) if it.course is not None else DEFAULT_UNITS
            loads[it.term] = loads.get(it.term, 0) + (it.units if it.units is not None else default)
    if len(cert.loads) != len(loads) or {e.term: e.units for e in cert.loads} != loads:
        bad.append("loads do not match the plan")
    state = ProgramState(satisfied=frozenset(satisfied), assignments=assigned)
    claimed = [(g.goal, g.value, g.limit, g.pass_) for g in cert.goals]
    recomputed = [
        [(o.result.goal, o.result.value, o.result.limit, o.result.pass_) for o in outcomes]
        for outcomes in (
            evaluate_goals(facts, idx, rules, state, strict=False),
            evaluate_goals(facts, idx, rules, state, strict=True),
        )
    ]
    if claimed not in recomputed:
        bad.append("goal results do not match the plan")
    for goal, result in zip(plan.goals, cert.goals, strict=False):
        if goal.hard and not result.pass_:
            bad.append(f"hard goal {goal.id} is not met")
    return bad


class _Tree:
    """Checks one program's assignments and evaluates its rule tree bottom-up."""

    def __init__(
        self, program: ProgramRules, assigned: dict[str, list[str]], facts: PlanFacts, idx: Index
    ) -> None:
        self.program, self.assigned, self.facts, self.idx = program, assigned, facts, idx
        self.problems: list[str] = []
        self.units: dict[str, list[Taken]] = {}  # unit path -> validated courses
        self.single: dict[str, int] = {}  # course key -> uses in units without double counting

    def check(self) -> bool:
        ok, _, _ = self.node(self.program.rules, self.program.id, Constraints())
        self.problems += [
            f"{key} fills {n} units of {self.program.id}" for key, n in self.single.items() if n > 1
        ]
        return ok

    def keys(self, skip: list[str]) -> set[str]:
        """Courses used in the program, leaving out units a share limit excepts."""
        return {
            t.key for path, used in self.units.items() if not excepted(path, skip) for t in used
        }

    def unit(self, path: str, selector: Selector, rules: Constraints) -> list[Taken]:
        """The courses assigned to one unit, each checked against the plan and the selector."""
        used: list[Taken] = []
        for code in self.assigned.get(path, []):
            taken = self.facts.taken.get(self.idx.canon(code))
            if taken is None or taken in used:
                self.problems.append(f"{path}: {code} is not in the plan, or is listed twice")
                continue
            if not self.idx.matches(selector, code):
                self.problems.append(f"{path}: {code} does not match the selector")
            if rules.no_pass_fail and taken.grading == "pass_fail":
                self.problems.append(f"{path}: {code} is taken Pass/Fail")
            if not grade_ok(taken.grade, rules.min_grade):
                self.problems.append(f"{path}: {code} is below the grade minimum")
            if not rules.allow_double_count:
                self.single[taken.key] = self.single.get(taken.key, 0) + 1
            used.append(taken)
        self.units[path] = used
        return used

    def node(
        self, node: AnyNode, path: str, inherited: Constraints
    ) -> tuple[bool, list[Taken], list[Selector]]:
        """(satisfied, courses used below the node, selectors below the node)."""
        own = node.constraints
        passed = Constraints(
            no_pass_fail=inherited.no_pass_fail or own.no_pass_fail,
            min_grade=stricter(inherited.min_grade, own.min_grade),
            allow_double_count=inherited.allow_double_count or own.allow_double_count,
        )
        if isinstance(node, SlotNode):
            selectors = [Selector(codes=node.any_of)]
            used = self.unit(path, selectors[0], passed)
            ok = len(used) == 1
        elif isinstance(node, SelectNode):
            selectors = [node.from_]
            used = self.unit(path, node.from_, passed)
            if node.count is not None:
                ok = len(used) == node.count  # exactly: constraints apply to these
            else:
                ok = sum(t.units for t in used) >= (node.units or 0)
        elif isinstance(node, GroupNode):
            results = [self.node(c, f"{path}/{c.id}", passed) for c in node.children]
            used = [t for _, courses, _ in results for t in courses]
            selectors = [s for _, _, found in results for s in found]
            done = sum(ok for ok, _, _ in results)
            ok = done == len(results) if node.all else done >= (node.n_of or 0)
        else:
            used, selectors, ok = [], [], True
            for part in node.parts:
                rules = part.constraints
                merged = Constraints(
                    no_pass_fail=passed.no_pass_fail or rules.no_pass_fail,
                    min_grade=stricter(passed.min_grade, rules.min_grade),
                    allow_double_count=passed.allow_double_count or rules.allow_double_count,
                )
                mine = self.unit(f"{path}/{part.id}", part.from_, merged)
                ok = ok and part.count[0] <= len(mine) <= part.count[1]
                ok = ok and self.holds(rules, mine, [part.from_])
                used += mine
                selectors.append(part.from_)
            ok = ok and len({t.key for t in used}) == len(used)  # one part per course
            if node.total.courses is not None:
                ok = ok and len(used) == node.total.courses
            else:
                ok = ok and sum(t.units for t in used) >= (node.total.units or 0)
        return ok and self.holds(own, used, selectors), used, selectors

    def holds(self, rules: Constraints, used: list[Taken], selectors: list[Selector]) -> bool:
        """The set constraints of one node, over the courses used below it."""
        if rules.same_sequence and used:
            sequences = self.idx.sequences(selectors).values()
            if not any(all(t.key in members for t in used) for members in sequences):
                return False
        if rules.in_order and any(out_of_order(a, b) for a in used for b in used):
            return False
        for limit in rules.max_from:
            if sum(self.idx.matches(limit.selector, t.code) for t in used) > limit.n:
                return False
        subjects = {t.code.split(" ")[0] for t in used}
        return rules.distinct_subjects is None or len(subjects) >= rules.distinct_subjects


def _is_fact(token: str, item: Taken, facts: PlanFacts) -> bool:
    """Is a non-course witness token (`kind:value`) true of the plan?"""
    kind, _, value = token.partition(":")
    plan = facts.plan
    if kind == "consent":
        return True
    if kind == "placement":
        credits = [c for c in plan.credits if c.kind == "placement"]
        return value in plan.placements or any(value in (c.label, c.maps_to) for c in credits)
    if kind == "standing":
        year = facts.class_year(item.term or plan.entry_term)
        return value in STANDINGS and year >= STANDINGS.index(value) + 1
    return kind == "program" and any(fnmatchcase(p.program_id, value) for p in plan.programs)


def _holds(expr: Expr, item: Taken, by: set[str], recs: Records, idx: Index, coreq: bool) -> bool:
    """Does `expr` hold for `item` when only the facts cited in `by` may be used?"""
    if expr.atom is None:
        met = sum(_holds(child, item, by, recs, idx, coreq) for child in expr.children)
        return met >= {"all": len(expr.children), "any": 1, "n_of": expr.n or 0}[expr.op]
    atom = expr.atom
    if atom.kind not in ("course", "concurrent"):
        return f"{atom.kind}:{atom.value}" in by
    same_term_ok = atom.kind == "concurrent" or coreq
    return any(
        t.ref in by
        and (t.order < item.order or (same_term_ok and t.order == item.order))
        and grade_ok(t.grade, atom.min_grade)
        for key in idx.alts(atom.value) - {item.key}
        for t in recs.get(key, [])
    )
