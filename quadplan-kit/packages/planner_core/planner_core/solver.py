"""CP-SAT model for program satisfaction (V07) and sharing limits (V08).

Variables (SPEC "Program satisfaction as a constraint model"):
- `x[c, u]`: course c is used for unit u (a slot, a select or a bounded_parts part); created
  only for eligible pairs.
- `s[n]`: node n is satisfied.
- `y[c, P]`: course c is used anywhere in program P.

Node semantics:
- slot: `sum x == s` (exactly one course when satisfied, none otherwise).
- select by count k: `sum x == k * s`; by units U: `sum units * x >= U * s`.
- bounded_parts: every part within `[min, max] * s`, the parts sum to `total * s`, and a
  course fills at most one part.
- group `all`: `s <= s[child]` for every child. Group `n_of`: at most n children are
  *active*, an inactive child's subtree takes no courses, and `n * s <= sum s[child]`.
- same_sequence: one indicator per sequence, at most one chosen, and a course may be used
  only if a chosen sequence contains it. in_order: two courses taken out of order cannot
  both be used. max_from: at most n used courses match the selector. distinct_subjects: the
  node is satisfied only if its courses span n subjects (the subject of the code as written
  in the plan).
- Within a program a course fills at most one unit, except units with `allow_double_count`.
  Each enrolment of a repeatable course is a course of its own (`Taken.uid`), and the n-th
  enrolment may be used in a unit only if the (n-1)-th is used there too.
- Share limit m between P and Q: `sum z[c] <= m + over` with `z[c] >= y[c, P] + y[c, Q] - 1`,
  where `y` leaves out units named in the limit's `except` and `over >= 0` is penalized.
  A solution with `over > 0` breaks the limit; the verifier reports it as V08.
- Residency: an indicator per program that holds only if the required share of the
  program's courses is taken in residence (reported by V09).

Objective, lexicographic in one weighted sum:
 1. maximize the weighted number of satisfied nodes, where a node outweighs its whole
    subtree (so "the program is satisfiable" is never traded for more satisfied sub-nodes,
    and an incomplete plan reports the smallest set of missing requirements);
 2. break as few rules as possible (residency indicators, courses shared beyond a limit);
 3. minimize the number of courses used. An unsatisfied node is given no courses.

Two solves, because proving that objective optimal is slow exactly when a plan is incomplete:
 1. Exact: every program's root is required. If this is feasible the plan satisfies its
    programs, and the solve only minimizes rule breaks and courses. This is the solve every
    certificate comes from.
 2. Best effort, only when (1) is infeasible: the full objective under a deterministic work
    limit (`BEST_EFFORT_WORK`). The plan is known to be incomplete; the unmet nodes reported
    are true for the assignment found, and when optimality was not proven the report says
    that the list may not be the smallest possible.

The solver runs single-threaded with a deterministic work limit, so equal inputs give equal
outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any

from ortools.sat.python import cp_model

from planner_core.dsl import AnyNode, excepted, residency_fraction, share_applies
from planner_core.index import Index, PlanFacts, Taken
from planner_core.models import BoundedPartsNode, CollegePolicy, GroupNode
from planner_core.tree import Compiled, Scope, out_of_order, selectors_below

#: Work limit (CP-SAT deterministic time) of the best-effort solve for unsatisfied plans.
BEST_EFFORT_WORK = 0.3
_MAX_OBJECTIVE = 2**60
_MAX_WEIGHT_RATIO = 1000


@dataclass
class SharedOver:
    """A share limit the solution exceeds: the programs count more courses in common."""

    program: str
    other: str
    max: int
    courses: list[str]


@dataclass
class Solution:
    #: "optimal", "feasible" (time limit hit; the unmet set may not be minimal) or "unknown".
    status: str = "optimal"
    #: Unit path -> courses assigned to it (only non-empty entries).
    assignments: dict[str, list[Taken]] = field(default_factory=dict)
    #: Node path -> satisfied (parts are not listed).
    satisfied: dict[str, bool] = field(default_factory=dict)
    #: Program id -> residency requirement holds (only programs that have one).
    residency_ok: dict[str, bool] = field(default_factory=dict)
    shared_over: list[SharedOver] = field(default_factory=list)

    def used(self, compiled: Compiled) -> dict[str, Taken]:
        """Key -> course, for every course assigned in the program."""
        found: dict[str, Taken] = {}
        for path in compiled.units:
            for taken in self.assignments.get(path, []):
                found[taken.uid] = taken
        return found


def node_weights(compiled: Compiled) -> dict[str, int]:
    """Objective weight per node: `weight` (relative to the smallest in the program) times
    one more than the total weight of the node's subtree."""
    nodes: list[tuple[str, AnyNode]] = []

    def collect(path: str, node: AnyNode) -> None:
        nodes.append((path, node))
        if isinstance(node, GroupNode):
            for child in node.children:
                collect(f"{path}/{child.id}", child)

    collect(compiled.program.id, compiled.program.rules)
    smallest = min(node.weight for _, node in nodes)
    ratio = {p: min(_MAX_WEIGHT_RATIO, max(1, round(n.weight / smallest))) for p, n in nodes}
    weights: dict[str, int] = {}

    def walk(path: str, node: AnyNode) -> int:
        below = 0
        if isinstance(node, GroupNode):
            below = sum(walk(f"{path}/{child.id}", child) for child in node.children)
        weights[path] = ratio[path] * (1 + below)
        return weights[path] + below

    walk(compiled.program.id, compiled.program.rules)
    return weights if sum(weights.values()) < _MAX_OBJECTIVE // 10**6 else ratio


class _Model:
    def __init__(
        self,
        facts: PlanFacts,
        idx: Index,
        college: CollegePolicy | None,
        allowed: Callable[[Taken], bool] | None,
    ) -> None:
        self.facts, self.idx, self.college, self.allowed = facts, idx, college, allowed
        self.model = cp_model.CpModel()
        self.x: dict[str, dict[str, Any]] = {}  # unit path -> key -> var
        self.s: dict[str, Any] = {}  # node path -> var, or None when it cannot be satisfied
        self.objective: list[Any] = []  # weighted s terms
        self._y: dict[tuple[str, str, tuple[str, ...]], Any] = {}

    def bool(self) -> Any:
        return self.model.new_bool_var("")

    # -------------------------------------------------------------- tree

    def vars_for(self, compiled: Compiled, path: str) -> dict[str, Any]:
        unit = compiled.units[path]
        pool = [t for t in unit.eligible if self.allowed is None or self.allowed(t)]
        xs = self.x[path] = {t.uid: self.bool() for t in pool}
        for taken in pool:  # enrolments of a repeatable course count in order within a unit
            if taken.nth > 1:
                earlier = xs.get(replace(taken, nth=taken.nth - 1).uid, 0)
                self.model.add(xs[taken.uid] <= earlier)
        return xs

    def node(self, compiled: Compiled, node: AnyNode, path: str, active: Any) -> Any:
        """Add the node's constraints; returns its satisfaction variable, or None when the
        node cannot be satisfied by this plan. `active` is None at the root (always active)."""
        m = self.model
        s: Any = None
        if isinstance(node, GroupNode):
            child_active = [self.bool() if node.n_of is not None else active for _ in node.children]
            if node.n_of is not None:
                m.add(sum(child_active) <= node.n_of)
                if active is not None:
                    for a in child_active:
                        m.add_implication(a, active)
            kids = [
                self.node(compiled, child, f"{path}/{child.id}", a)
                for child, a in zip(node.children, child_active, strict=True)
            ]
            possible = [kid for kid in kids if kid is not None]
            need = len(kids) if node.all else (node.n_of or 0)
            if len(possible) >= need:
                s = self.bool()
                if node.all:
                    for kid in possible:
                        m.add_implication(s, kid)
                else:
                    m.add(need * s <= sum(possible))
        elif isinstance(node, BoundedPartsNode):
            s = self._bounded(compiled, node, path)
        else:
            unit = compiled.units[path]
            units = {t.uid: t.units for t in unit.eligible}
            xs = self.vars_for(compiled, path)
            if unit.need_units is None and len(xs) >= unit.need:
                s = self.bool()
                m.add(sum(xs.values()) == unit.need * s)
            elif unit.need_units is not None and sum(units[k] for k in xs) >= unit.need_units:
                s = self.bool()
                m.add(sum(units[k] * var for k, var in xs.items()) >= unit.need_units * s)
                m.add(sum(xs.values()) <= len(xs) * s)
            else:
                self._zero(xs)
        if s is not None and active is not None:
            m.add_implication(s, active)
        self.s[path] = s
        return s

    def _zero(self, xs: dict[str, Any]) -> None:
        for var in xs.values():
            self.model.add(var == 0)

    def _bounded(self, compiled: Compiled, node: BoundedPartsNode, path: str) -> Any:
        m = self.model
        parts = {part.id: self.vars_for(compiled, f"{path}/{part.id}") for part in node.parts}
        reach = sum(min(len(parts[p.id]), p.count[1]) for p in node.parts)
        short = any(len(parts[p.id]) < p.count[0] for p in node.parts)
        if short or (node.total.courses is not None and reach < node.total.courses):
            for xs in parts.values():
                self._zero(xs)
            return None
        s = self.bool()
        everything: list[Any] = []
        units_terms: list[Any] = []
        by_key: dict[str, list[Any]] = {}
        for part in node.parts:
            unit = compiled.units[f"{path}/{part.id}"]
            units = {t.uid: t.units for t in unit.eligible}
            xs = parts[part.id]
            count = sum(xs.values())
            m.add(count >= part.count[0] * s)
            m.add(count <= part.count[1] * s)
            for key, var in xs.items():
                everything.append(var)
                units_terms.append(units[key] * var)
                by_key.setdefault(key, []).append(var)
        if node.total.courses is not None:
            m.add(sum(everything) == node.total.courses * s)
        else:
            m.add(sum(units_terms) >= (node.total.units or 0) * s)
        for group in by_key.values():
            if len(group) > 1:
                m.add_at_most_one(group)
        return s

    # -------------------------------------------------------------- program-level

    def program(self, compiled: Compiled) -> None:
        self.node(compiled, compiled.program.rules, compiled.program.id, None)
        weights = node_weights(compiled)
        self.objective += [
            weights[path] * s for path, s in self.s.items() if path in weights and s is not None
        ]
        single: dict[str, list[Any]] = {}
        for path, unit in compiled.units.items():
            if not unit.double_count:
                for key, var in self.x.get(path, {}).items():
                    single.setdefault(key, []).append(var)
        for group in single.values():
            if len(group) > 1:
                self.model.add_at_most_one(group)
        for scope in compiled.scopes:
            self._scope(compiled, scope)

    def _scope(self, compiled: Compiled, scope: Scope) -> None:
        m, c = self.model, scope.constraints
        pairs = [
            (self.facts.taken[key], var)
            for path in scope.units
            for key, var in self.x.get(path, {}).items()
        ]
        if c.same_sequence:
            sequences = self.idx.sequences(selectors_below(compiled, scope))
            keys = {t.key for t, _ in pairs}
            chosen = {name: self.bool() for name, members in sequences.items() if members & keys}
            m.add(sum(chosen.values()) <= 1)
            for taken, var in pairs:
                m.add(var <= sum(q for name, q in chosen.items() if taken.key in sequences[name]))
        if c.in_order:
            for i, (a, var_a) in enumerate(pairs):
                for b, var_b in pairs[i + 1 :]:
                    if out_of_order(a, b):
                        m.add_at_most_one([var_a, var_b])
        for limit in c.max_from:
            m.add(sum(var for t, var in pairs if self.idx.counts(limit, t.code)) <= limit.n)
        owner = self.s.get(scope.owner)
        if c.distinct_subjects is not None and owner is not None:
            by_subject: dict[str, list[Any]] = {}
            for taken, var in pairs:
                by_subject.setdefault(taken.code.split(" ")[0], []).append(var)
            seen = []
            for group in by_subject.values():
                flag = self.bool()
                m.add(flag <= sum(group))
                seen.append(flag)
            m.add(sum(seen) >= c.distinct_subjects * owner)

    def y(self, compiled: Compiled, key: str, skip: tuple[str, ...] = ()) -> Any:
        """Course `key` is used in the program, not counting units named in `skip`."""
        cache_key = (compiled.program.id, key, skip)
        if cache_key not in self._y:
            found = [
                (path, self.x[path][key])
                for path in compiled.units
                if key in self.x.get(path, {}) and not excepted(path, list(skip))
            ]
            var: Any = None
            if len(found) == 1:
                var = found[0][1]
            elif found and not any(compiled.units[path].double_count for path, _ in found):
                var = sum(v for _, v in found)  # at most one of them is 1
            elif found:
                var = self.bool()
                for _, v in found:
                    self.model.add_implication(v, var)
                self.model.add(var <= sum(v for _, v in found))
            self._y[cache_key] = var
        return self._y[cache_key]

    def keys(self, compiled: Compiled) -> list[str]:
        return sorted({key for path in compiled.units for key in self.x.get(path, {})})


def solve(
    programs: list[Compiled],
    facts: PlanFacts,
    idx: Index,
    college: CollegePolicy | None,
    *,
    time_limit_s: float = 2.0,
    allowed: Callable[[Taken], bool] | None = None,
    exact_only: bool = False,
) -> Solution:
    """Solve the assignment for the given programs. `allowed` restricts which plan courses
    may be used (the timing check re-solves with on-time courses only). `exact_only` skips
    the best-effort solve: when the programs cannot all be satisfied the answer is an empty
    Solution (nothing satisfied), for callers that only ask "can they be?"."""
    if not programs:
        return Solution()
    exact = _solve(
        programs,
        facts,
        idx,
        college,
        allowed,
        time_limit_s,
        require_roots=True,
        exact_only=exact_only,
    )
    if exact is not None:
        return exact
    if exact_only:
        return Solution()
    best = _solve(programs, facts, idx, college, allowed, time_limit_s, require_roots=False)
    assert best is not None
    return best


def _solve(
    programs: list[Compiled],
    facts: PlanFacts,
    idx: Index,
    college: CollegePolicy | None,
    allowed: Callable[[Taken], bool] | None,
    time_limit_s: float,
    *,
    require_roots: bool,
    exact_only: bool = False,
) -> Solution | None:
    """One CP-SAT solve. With `require_roots` it returns None when the solver proves that
    not every program can be satisfied (the caller then runs the best-effort solve). A solve
    that ends without any answer returns a Solution with status "unknown"."""
    b = _Model(facts, idx, college, allowed)
    m = b.model
    for compiled in programs:
        b.program(compiled)
    roots = [b.s[c.program.id] for c in programs]
    if any(root is None for root in roots):
        if exact_only:
            return None
        require_roots = False  # some program cannot be satisfied: go straight to best effort
    for root in roots if require_roots else []:
        m.add(root == 1)

    used = [(c, key, b.y(c, key)) for c in programs for key in b.keys(c)]
    residency: dict[str, Any] = {}
    for compiled in programs:
        fraction = residency_fraction(compiled.program, college)
        mine = [(key, var) for c, key, var in used if c is compiled]
        if fraction is None or not mine:
            continue
        frac = Fraction(fraction).limit_denominator(1000)
        home = sum(var for key, var in mine if facts.taken[key].enrolled)
        flag = b.bool()
        slack = frac.numerator * len(mine)
        total = sum(var for _, var in mine)
        m.add(frac.denominator * home - frac.numerator * total + slack * (1 - flag) >= 0)
        residency[compiled.program.id] = flag

    limits: list[tuple[Compiled, Compiled, int, tuple[str, ...]]] = []
    excess: list[Any] = []
    for p in programs:
        for limit in p.program.policy.share:
            for q in programs:
                if q is p or not share_applies(limit.with_, q.program, college):
                    continue
                skip = tuple(limit.except_)
                limits.append((p, q, limit.max, skip))
                both = []
                for key in b.keys(p):
                    in_p, in_q = b.y(p, key, skip), b.y(q, key, skip)
                    if in_p is not None and in_q is not None:
                        z = b.bool()
                        m.add(z >= in_p + in_q - 1)
                        both.append(z)
                if len(both) > limit.max:
                    over = m.new_int_var(0, len(both) - limit.max, "")
                    m.add(sum(both) <= limit.max + over)
                    excess.append((over, len(both) - limit.max))

    # Lexicographic objective as one weighted sum: satisfied nodes, then rule breaks
    # (residency, sharing beyond a limit), then courses used.
    n_used = len(used) + 1
    n_breaks = len(residency) + sum(most for _, most in excess) + 1
    m.maximize(
        n_used * n_breaks * sum(b.objective)
        + n_used * (sum(residency.values()) - sum(over for over, _ in excess))
        - sum(var for _, _, var in used)
    )

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    # The model is close to a matching problem: a full LP relaxation, loaded up front, lets
    # the solver prove optimality (or infeasibility) several times faster than the defaults.
    solver.parameters.linearization_level = 2
    solver.parameters.add_lp_constraints_lazily = False
    solver.parameters.max_time_in_seconds = time_limit_s
    if not require_roots:
        solver.parameters.max_deterministic_time = BEST_EFFORT_WORK
    status = solver.solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if require_roots and status == cp_model.INFEASIBLE:
            return None
        return Solution(status="unknown", satisfied={p: False for c in programs for p in c.below})

    out = Solution(status="optimal" if status == cp_model.OPTIMAL else "feasible")
    for path, xs in b.x.items():
        chosen = [facts.taken[key] for key, var in xs.items() if solver.boolean_value(var)]
        if chosen:
            out.assignments[path] = sorted(chosen, key=lambda t: (t.order, t.code))
    out.satisfied = {p: s is not None and solver.boolean_value(s) for p, s in b.s.items()}
    out.residency_ok = {p: solver.boolean_value(flag) for p, flag in residency.items()}
    for p, q, most, skip in limits:
        in_q = {
            t.uid
            for path in q.units
            if not excepted(path, list(skip))
            for t in out.assignments.get(path, [])
        }
        shared = sorted(
            {
                t.code
                for path in p.units
                if not excepted(path, list(skip))
                for t in out.assignments.get(path, [])
                if t.uid in in_q
            }
        )
        if len(shared) > most:
            out.shared_over.append(SharedOver(p.program.id, q.program.id, most, shared))
    return out
