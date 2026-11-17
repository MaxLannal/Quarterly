"""Program checks built on the solver: V07 (rule trees), V08 (sharing and program relations),
V12 (Pass/Fail), per-node progress, and the on-time re-solve used by V10.

How codes are assigned:
- V07: one error per unmet requirement of an unsatisfied program, found by walking the tree
  from the root: an `all` group reports its unmet children, an `n_of` group reports itself
  with one hint per unfinished option, a leaf reports what it still needs.
- V08: share limits are soft in the model (satisfying nodes comes first, then sharing as
  little beyond a limit as possible). Every limit the solution exceeds is a V08 error naming
  the shared courses, and the program that declares the limit also gets a V07 error at its
  root: it is complete only on paper. `requires` / `excludes` between programs are V08 too.
- V12: a course taken Pass/Fail never counts toward a node that forbids it. It is an error
  only where the plan relies on it: the course would fit a requirement that is still unmet,
  or the program is unmet but would be met if its Pass/Fail courses had letter grades (the
  solver may have filled the course's own requirement with another course and left a
  different one open; the second test finds the course whatever the solver picked).

Progress shown for an unmet unit is tentative (eligible courses not used elsewhere in the
program, chosen greedily); only the solver's assignments enter the certificate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from planner_core.dsl import AnyNode
from planner_core.index import Index, PlanFacts, Taken, describe_selector
from planner_core.models import (
    BoundedPartsNode,
    CollegePolicy,
    Constraints,
    GroupNode,
    Issue,
    NodeProgress,
    PlanState,
    ProgramRules,
    RuleSet,
)
from planner_core.solver import Solution, solve
from planner_core.tree import Compiled, Unit, compile_program, selectors_below


@dataclass
class ProgramsResult:
    compiled: dict[str, Compiled] = field(default_factory=dict)  # by program id
    solution: Solution = field(default_factory=Solution)
    v07: list[Issue] = field(default_factory=list)
    v08: list[Issue] = field(default_factory=list)
    v12: list[Issue] = field(default_factory=list)
    progress: list[NodeProgress] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    #: Programs whose own share limit is exceeded: complete on paper, but not satisfied.
    blocked: set[str] = field(default_factory=set)

    def satisfied(self, program_id: str) -> bool:
        return program_id not in self.blocked and self.solution.satisfied.get(program_id, False)

    def satisfied_programs(self) -> frozenset[str]:
        return frozenset(p for p in self.compiled if self.satisfied(p))

    def assignments(self) -> dict[str, list[str]]:
        """Unit path -> course codes as written in the plan."""
        return {
            path: [t.code for t in courses] for path, courses in self.solution.assignments.items()
        }


def plan_programs(plan: PlanState, rules: RuleSet) -> list[ProgramRules]:
    """The plan's programs that have rules loaded, in plan order (each once)."""
    by_id = {p.id: p for p in rules.programs}
    seen: list[ProgramRules] = []
    for entry in plan.programs:
        program = by_id.get(entry.program_id)
        if program is not None and program not in seen:
            seen.append(program)
    return seen


def check_programs(
    plan: PlanState, rules: RuleSet, facts: PlanFacts, idx: Index, time_limit_s: float
) -> ProgramsResult:
    programs = plan_programs(plan, rules)
    compiled = [compile_program(p, facts, idx) for p in programs]
    out = ProgramsResult(compiled={c.program.id: c for c in compiled})
    sol = out.solution = solve(compiled, facts, idx, rules.college, time_limit_s=time_limit_s)
    out.v08 += _relations(plan, programs)
    if sol.status == "unknown":
        out.v07 += [
            Issue(
                code="V07",
                level="error",
                message=f"{c.program.id}: the requirements could not be checked within the "
                "time limit.",
                node_id=c.program.id,
                fix_hints=["Try again; if this keeps happening, report it."],
            )
            for c in compiled
        ]
        return out
    if sol.status == "feasible":
        out.assumptions.append(
            "The solver stopped at its work limit; the list of missing requirements may not "
            "be the smallest possible."
        )
    for over in sol.shared_over:
        out.blocked.add(over.program)
        extra = len(over.courses) - over.max
        out.v08.append(
            Issue(
                code="V08",
                level="error",
                message=f"{over.program} may share at most {over.max} course(s) with "
                f"{over.other}, but {len(over.courses)} count toward both: "
                f"{', '.join(over.courses)}.",
                course_ids=over.courses,
                node_id=over.program,
                fix_hints=[
                    f"Add {extra} more course(s) that can count toward {over.program} or "
                    f"{over.other}, so that at most {over.max} are shared."
                ],
            )
        )
    for c in compiled:
        pid = c.program.id
        tentative = _tentative(c, sol, idx)
        rows = _progress(c, sol, tentative)
        if pid in out.blocked:
            rows[0].satisfied = False
        out.progress += rows
        if not sol.satisfied.get(pid, False):
            walker = _Unmet(c, sol, tentative, facts, idx)
            walker.walk(c.program.rules, pid)
            out.v07 += walker.issues
            out.v12 += walker.pass_fail_issues()
            out.v12 += _relied_on_pass_fail(c, out.v12, facts, idx, rules.college, time_limit_s)
        elif pid in out.blocked:
            out.v07.append(
                Issue(
                    code="V07",
                    level="error",
                    message=f"{pid}: the requirements are met only by counting courses that "
                    "also count toward another program beyond the sharing limit (see V08).",
                    node_id=pid,
                    fix_hints=["Add courses so that the programs do not rely on the same ones."],
                )
            )
    return out


def _pass_fail_issue(taken: Taken, unit: Unit) -> Issue:
    return Issue(
        code="V12",
        level="error",
        message=f"{taken.code} is taken Pass/Fail, so it cannot count toward "
        f"{unit.label or unit.path}, which requires a letter grade.",
        course_ids=[taken.code],
        term_ids=[taken.term] if taken.term else [],
        node_id=unit.path,
        fix_hints=[f"Take {taken.code} for a letter grade."],
    )


def _relied_on_pass_fail(
    compiled: Compiled,
    known: list[Issue],
    facts: PlanFacts,
    idx: Index,
    college: CollegePolicy | None,
    time_limit_s: float,
) -> list[Issue]:
    """V12 for an unmet program that would be met if its Pass/Fail courses had letter grades:
    one issue per Pass/Fail course that the "what if" assignment puts where it is forbidden."""
    if not any(unit.blocked_pass_fail for unit in compiled.units.values()):
        return []
    what_if = compile_program(compiled.program, facts, idx, count_pass_fail=True)
    sol = solve([what_if], facts, idx, college, time_limit_s=time_limit_s, exact_only=True)
    if not sol.satisfied.get(compiled.program.id, False):
        return []
    seen = {(issue.node_id, code) for issue in known for code in issue.course_ids}
    return [
        _pass_fail_issue(taken, unit)
        for path, unit in compiled.units.items()
        for taken in sol.assignments.get(path, [])
        if taken in unit.blocked_pass_fail and (path, taken.code) not in seen
    ]


def _relations(plan: PlanState, programs: list[ProgramRules]) -> list[Issue]:
    issues: list[Issue] = []
    listed = [p.program_id for p in plan.programs]
    for program in programs:
        others = [p for p in listed if p != program.id]
        for pattern in program.policy.requires:
            if not any(fnmatchcase(o, pattern) for o in others):
                issues.append(
                    Issue(
                        code="V08",
                        level="error",
                        message=f"{program.id} requires the program {pattern}, which is not "
                        "in this plan.",
                        node_id=program.id,
                        fix_hints=[f"Add {pattern} to the plan, or remove {program.id}."],
                    )
                )
        for pattern in program.policy.excludes:
            for other in others:
                if fnmatchcase(other, pattern):
                    issues.append(
                        Issue(
                            code="V08",
                            level="error",
                            message=f"{program.id} cannot be combined with {other}.",
                            node_id=program.id,
                            fix_hints=[f"Remove {program.id} or {other} from the plan."],
                        )
                    )
    return issues


# --------------------------------------------------------------------------------------------
# Tentative progress for unmet units
# --------------------------------------------------------------------------------------------


def _unit_satisfied(compiled: Compiled, path: str, sol: Solution) -> bool:
    unit = compiled.units[path]
    owner = path.rsplit("/", 1)[0] if unit.kind == "part" else path
    return sol.satisfied.get(owner, False)


def _tentative(compiled: Compiled, sol: Solution, idx: Index) -> dict[str, list[Taken]]:
    """Unit path -> courses shown as progress: the solver's assignment for satisfied units,
    a greedy pick of unused eligible courses for the others."""
    used = set(sol.used(compiled))
    same_sequence = {s.path: s for s in compiled.scopes if s.constraints.same_sequence}
    room: dict[str, int] = {}  # bounded_parts path -> courses still allowed by its total
    shown: dict[str, list[Taken]] = {}
    for path, unit in compiled.units.items():
        if _unit_satisfied(compiled, path, sol):
            shown[path] = sol.assignments.get(path, [])
            continue
        pool = [t for t in unit.eligible if unit.double_count or t.uid not in used]
        if path in same_sequence:
            sequences = idx.sequences(selectors_below(compiled, same_sequence[path]))
            groups = [[t for t in pool if t.key in members] for members in sequences.values()]
            pool = max(groups, key=len, default=[])
        cap = unit.cap if unit.cap is not None else len(pool)
        if unit.kind == "part":
            parent = path.rsplit("/", 1)[0]
            total = _bounded_total(compiled, parent)
            if total is not None:
                cap = min(cap, room.setdefault(parent, total))
                room[parent] -= min(cap, len(pool))
        shown[path] = pool[:cap]
        if not unit.double_count:
            used |= {t.uid for t in shown[path]}
    return shown


def _find(compiled: Compiled, path: str) -> AnyNode:
    node: AnyNode = compiled.program.rules
    for part in path.split("/")[1:]:
        assert isinstance(node, GroupNode)
        node = next(child for child in node.children if child.id == part)
    return node


def _bounded_total(compiled: Compiled, path: str) -> int | None:
    node = _find(compiled, path)
    assert isinstance(node, BoundedPartsNode)
    return node.total.courses


def _progress(
    compiled: Compiled, sol: Solution, shown: dict[str, list[Taken]]
) -> list[NodeProgress]:
    out: list[NodeProgress] = []
    pid = compiled.program.id

    def unit_row(path: str, unit: Unit, satisfied: bool) -> NodeProgress:
        courses = shown.get(path, [])
        by_units = unit.need_units is not None
        have = sum(t.units for t in courses) if by_units else len(courses)
        return NodeProgress(
            program_id=pid,
            node_id=path,
            label=unit.label,
            satisfied=satisfied,
            have=have,
            need=unit.need_units if unit.need_units is not None else unit.need,
            unit="units" if by_units else "courses",
            courses=[t.code for t in courses],
        )

    def walk(path: str, node: AnyNode) -> None:
        ok = sol.satisfied.get(path, False)
        if isinstance(node, GroupNode):
            done = sum(sol.satisfied.get(f"{path}/{c.id}", False) for c in node.children)
            need = len(node.children) if node.all else (node.n_of or 0)
            out.append(
                NodeProgress(
                    program_id=pid,
                    node_id=path,
                    label=node.label,
                    satisfied=ok,
                    have=min(done, need),
                    need=need,
                )
            )
            for child in node.children:
                walk(f"{path}/{child.id}", child)
        elif isinstance(node, BoundedPartsNode):
            rows = [
                unit_row(f"{path}/{p.id}", compiled.units[f"{path}/{p.id}"], False)
                for p in node.parts
            ]
            for row in rows:
                row.satisfied = row.have >= row.need
            courses = [t for p in node.parts for t in shown.get(f"{path}/{p.id}", [])]
            by_units = node.total.courses is None
            out.append(
                NodeProgress(
                    program_id=pid,
                    node_id=path,
                    label=node.label,
                    satisfied=ok,
                    have=sum(t.units for t in courses) if by_units else len(courses),
                    need=(node.total.units or 0) if by_units else (node.total.courses or 0),
                    unit="units" if by_units else "courses",
                    courses=[t.code for t in courses],
                )
            )
            out.extend(rows)
        else:
            out.append(unit_row(path, compiled.units[path], ok))

    walk(pid, compiled.program.rules)
    return out


# --------------------------------------------------------------------------------------------
# V07 / V12 messages
# --------------------------------------------------------------------------------------------


def describe_constraints(c: Constraints, unit: Unit | None = None) -> str:
    notes: list[str] = []
    if c.same_sequence:
        notes.append("all from one sequence")
    if c.in_order:
        notes.append("taken in order")
    for limit in c.max_from:
        how = " (by the code enrolled under)" if limit.as_enrolled else ""
        notes.append(f"at most {limit.n} from {describe_selector(limit.selector)}{how}")
    if c.distinct_subjects:
        notes.append(f"from at least {c.distinct_subjects} subjects")
    if unit is not None and unit.no_pass_fail:
        notes.append("letter grades only")
    if unit is not None and unit.min_grade:
        notes.append(f"grade {unit.min_grade} or higher")
    return f" ({'; '.join(notes)})" if notes else ""


class _Unmet:
    """Walks an unsatisfied program and writes one V07 issue per unmet requirement."""

    def __init__(
        self,
        compiled: Compiled,
        sol: Solution,
        shown: dict[str, list[Taken]],
        facts: PlanFacts,
        idx: Index,
    ) -> None:
        self.c, self.sol, self.shown = compiled, sol, shown
        self.facts, self.idx = facts, idx
        self.issues: list[Issue] = []
        self.unmet_units: list[str] = []

    def ok(self, path: str) -> bool:
        return self.sol.satisfied.get(path, False)

    def issue(self, path: str, message: str, hints: list[str], courses: list[str]) -> None:
        for item in self.facts.placeholders:
            if item.slot_ref == path or (item.slot_ref or "").startswith(path + "/"):
                hints.append(f"Replace the placeholder in {item.term} with a course.")
        self.issues.append(
            Issue(
                code="V07",
                level="error",
                message=message,
                node_id=path,
                course_ids=sorted(set(courses)),
                fix_hints=hints,
            )
        )

    def walk(self, node: AnyNode, path: str) -> None:
        label = node.label or path
        if isinstance(node, GroupNode):
            open_children = [c for c in node.children if not self.ok(f"{path}/{c.id}")]
            if node.all and open_children:
                for child in open_children:
                    self.walk(child, f"{path}/{child.id}")
                return
            self.unmet_units += [
                u for c in open_children for u in self.c.below[f"{path}/{c.id}"] if not self.ok(u)
            ]
            done = len(node.children) - len(open_children)
            need = len(node.children) if node.all else (node.n_of or 0)
            hints = [f"Complete {c.label or f'{path}/{c.id}'}." for c in open_children[:6]]
            notes = describe_constraints(node.constraints)
            if done >= need:
                message = f"{label}: its courses do not meet the rule{notes}."
                hints = ["Choose courses that meet the rule."]
            else:
                message = f"{label}: {done} of {need} required parts are complete{notes}."
            self.issue(path, message, hints, [])
        elif isinstance(node, BoundedPartsNode):
            pieces, hints, courses = [], [], []
            for part in node.parts:
                unit = self.c.units[f"{path}/{part.id}"]
                have = self.shown.get(unit.path, [])
                self.unmet_units.append(unit.path)
                courses += self._blocked(unit)
                lo, hi = part.count
                pieces.append(f"{part.label or part.id} {len(have)} of {lo}-{hi}")
                if len(have) < lo:
                    hints.append(
                        f"Add {lo - len(have)} more for {part.label or part.id}: "
                        f"{describe_selector(unit.selector, self.idx)}"
                        f"{describe_constraints(part.constraints, unit)}."
                    )
            total = node.total.courses
            goal = f"{total} courses" if total is not None else f"{node.total.units} units"
            have_all = sum(len(self.shown.get(f"{path}/{p.id}", [])) for p in node.parts)
            if not hints:
                hints.append(f"Add courses to reach {goal} across the parts.")
            self.issue(
                path,
                f"{label}: needs {goal} in total, has {have_all} "
                f"({'; '.join(pieces)}){describe_constraints(node.constraints)}.",
                hints,
                courses,
            )
        else:
            unit = self.c.units[path]
            self.unmet_units.append(path)
            have = self.shown.get(path, [])
            where = describe_selector(unit.selector, self.idx)
            notes = describe_constraints(node.constraints, unit)
            short = unit.need - len(have)
            if unit.kind == "slot":
                message = f"{label}: needs {where}{notes}."
                hints = [f"Add {where}."]
            elif unit.need_units is not None:
                got = sum(t.units for t in have)
                message = (
                    f"{label}: {got} of {unit.need_units} units; "
                    f"{unit.need_units - got} more needed from {where}{notes}."
                )
                hints = [f"Add {unit.need_units - got} more units from {where}."]
            else:
                message = (
                    f"{label}: {len(have)} of {unit.need} courses; "
                    f"{short} more needed from {where}{notes}."
                )
                hints = [f"Add {short} more course(s) from {where}."]
            if unit.kind != "slot" and unit.need_units is None and short <= 0:
                message = f"{label}: the courses from {where} do not meet the rule{notes}."
                hints = ["Choose courses that meet the rule."]
            self.issue(path, message, hints + self._grade_notes(unit), self._blocked(unit))

    def _blocked(self, unit: Unit) -> list[str]:
        return [t.code for t in [*unit.blocked_pass_fail, *unit.blocked_grade]]

    def _grade_notes(self, unit: Unit) -> list[str]:
        return [
            f"{t.code} has grade {t.grade}, below the minimum {unit.min_grade}, so it does "
            "not count here."
            for t in unit.blocked_grade
        ]

    def pass_fail_issues(self) -> list[Issue]:
        issues: list[Issue] = []
        for path in self.unmet_units:
            unit = self.c.units[path]
            issues += [_pass_fail_issue(taken, unit) for taken in unit.blocked_pass_fail]
        return issues


# --------------------------------------------------------------------------------------------
# On-time re-solve (V10)
# --------------------------------------------------------------------------------------------


def late_courses(
    result: ProgramsResult,
    program_id: str,
    on_time: Callable[[Taken], bool],
    facts: PlanFacts,
    idx: Index,
    college: CollegePolicy | None,
    time_limit_s: float,
) -> list[Taken] | None:
    """Can `program_id` be satisfied by on-time courses alone? Returns None when it can.
    Otherwise returns the late courses the full solution relies on (an empty list when the
    program is not satisfied at all). The solver may have picked a late course although an
    on-time one would do, so a late pick triggers a second solve with on-time courses only."""
    compiled = result.compiled[program_id]
    if not result.satisfied(program_id):
        return []
    late = [t for t in result.solution.used(compiled).values() if not on_time(t)]
    if not late:
        return None
    again = solve([compiled], facts, idx, college, time_limit_s=time_limit_s, allowed=on_time)
    if again.satisfied.get(program_id, False):
        return None
    return sorted(late, key=lambda t: (t.order, t.code))
