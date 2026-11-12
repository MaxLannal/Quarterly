"""Goal predicates (V11): one function per goal type in SPEC "Goal predicates".

Each predicate returns a `GoalOutcome` holding the `GoalResult` that goes into the
certificate (`value`, `limit`, `pass`). The certificate checker recomputes the same results
through `evaluate_goals`, so this module is solver-free arithmetic over the plan.

Conventions:
- A term's courses are its enrolled course items; counts also include placeholders.
- A term-scoped goal looks at its term. A career-scoped per-term goal looks at every Autumn,
  Winter and Spring quarter that has courses (Summer and empty quarters are skipped).
- "Done by T" means taken in T or earlier (credits count); cross-listed, equivalent and
  replacing courses count as the course.
- Courses without an attribute value contribute 0 and are listed as an assumption.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from planner_core.dsl import iter_nodes, iter_parts
from planner_core.index import Index, PlanFacts, Taken
from planner_core.models import (
    BxmsGoal,
    ChallengeGoal,
    CourseLoadGoal,
    DifficultyCapGoal,
    GoalResult,
    GraduateByGoal,
    InterestGoal,
    LanguageGoal,
    LightQuarterGoal,
    PremedGoal,
    ProgramRules,
    ProtectGpaGoal,
    RuleSet,
    SelectNode,
    SlotNode,
    StudyAbroadGoal,
    WorkloadHoursGoal,
)
from planner_core.terms import parse_term, resolve_term_ref, term_key

#: Defaults on the 1-5 forum scales when a goal does not set its own threshold.
VERY_HARD = 4.0
STRICT_GRADING = 4.0

AnyGoal = (
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
    | LanguageGoal
)


@dataclass(frozen=True)
class ProgramState:
    """What goal predicates may know about program satisfaction."""

    satisfied: frozenset[str] = frozenset()  # program ids whose rule tree is satisfied
    assignments: Mapping[str, Sequence[str]] = field(default_factory=dict)  # unit -> codes


@dataclass
class GoalOutcome:
    result: GoalResult
    message: str = ""
    terms: list[str] = field(default_factory=list)
    courses: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    #: 1.0 = met; lower = further from the goal (shown with soft-goal warnings).
    score: float = 1.0


@dataclass
class _Ctx:
    facts: PlanFacts
    idx: Index
    rules: RuleSet
    state: ProgramState
    strict: bool

    def terms(self, goal: AnyGoal) -> list[str]:
        if goal.term is not None:
            return [goal.term]
        return [t for t in self.facts.terms if parse_term(t)[1] != "SU"]

    def courses(self, term: str) -> list[Taken]:
        return self.facts.by_term.get(term, [])

    def attribute(self, taken: Taken, key: str, missing: set[str], upper: bool = False) -> float:
        value = self.idx.attribute(taken.code, key)
        if value is None:
            missing.add(taken.code)
            return 0.0
        return value.ci_high if upper and value.ci_high is not None else value.value

    def program(self, program_id: str) -> ProgramRules | None:
        listed = {p.program_id for p in self.facts.plan.programs}
        return next((p for p in self.rules.programs if p.id == program_id and p.id in listed), None)

    def deadline(self, ref: str) -> str:
        return resolve_term_ref(ref, self.facts.plan.entry_term)


def _ratio(value: float, limit: float) -> float:
    low, high = sorted((abs(value), abs(limit)))
    return round(low / high, 2) if high else 0.0


def _result(goal: AnyGoal, value: float | None, limit: float | None, ok: bool) -> GoalResult:
    rounded = round(value, 4) if value is not None else None
    return GoalResult(goal=goal.id, value=rounded, limit=limit, **{"pass": ok})


def _unknown(missing: set[str], what: str) -> list[str]:
    if not missing:
        return []
    return [f"No {what} estimate for {', '.join(sorted(missing))}; counted as 0."]


def _course_load(goal: CourseLoadGoal, ctx: _Ctx) -> GoalOutcome:
    counts = {t: ctx.facts.course_count(t) for t in ctx.terms(goal)}
    over = [t for t, n in counts.items() if goal.max_courses is not None and n > goal.max_courses]
    under = [t for t, n in counts.items() if goal.min_courses is not None and n < goal.min_courses]
    use_max = bool(over) or (goal.max_courses is not None and not under)
    limit = goal.max_courses if use_max else goal.min_courses
    pick = max if use_max else min
    value = float(pick(counts.values(), default=0))
    ok = not over and not under
    bounds = (
        f"{goal.min_courses or 0}-{goal.max_courses if goal.max_courses is not None else 'any'}"
    )
    return GoalOutcome(
        _result(goal, value, limit, ok),
        message=f"Course load outside {bounds} courses in {', '.join(over + under)}.",
        terms=over + under,
        hints=[f"Move a course out of {t}." for t in over]
        + [f"Add a course to {t}." for t in under],
        score=1.0 if ok else _ratio(value, float(limit or 0)),
    )


def _workload(goal: WorkloadHoursGoal, ctx: _Ctx) -> GoalOutcome:
    missing: set[str] = set()
    upper = goal.strict or ctx.strict
    sums = {
        t: sum(ctx.attribute(c, "workload_hours", missing, upper) for c in ctx.courses(t))
        for t in ctx.terms(goal)
    }
    if goal.aggregate == "career_average" and goal.term is None:
        value = sum(sums.values()) / len(sums) if sums else 0.0
        over = [] if value <= goal.max_hours else sorted(sums, key=lambda t: -sums[t])[:3]
    else:
        value = max(sums.values(), default=0.0)
        over = [t for t, hours in sums.items() if hours > goal.max_hours]
    ok = value <= goal.max_hours
    return GoalOutcome(
        _result(goal, value, goal.max_hours, ok),
        message=f"Estimated workload is {value:.1f} hours/week against a limit of "
        f"{goal.max_hours:g} ({', '.join(over)}).",
        terms=over,
        hints=[f"Swap a heavy course out of {t}." for t in over],
        assumptions=_unknown(missing, "workload"),
        score=1.0 if ok else _ratio(value, goal.max_hours),
    )


def _difficulty_cap(goal: DifficultyCapGoal, ctx: _Ctx) -> GoalOutcome:
    missing: set[str] = set()
    threshold = goal.very_hard_threshold if goal.very_hard_threshold is not None else VERY_HARD
    index: dict[str, float] = {}
    hard: dict[str, int] = {}
    for term in ctx.terms(goal):
        values = [ctx.attribute(c, "difficulty", missing) for c in ctx.courses(term)]
        index[term], hard[term] = sum(values), sum(v >= threshold for v in values)
    over_index = [t for t in index if goal.max_index is not None and index[t] > goal.max_index]
    over_hard = [t for t in hard if goal.max_very_hard is not None and hard[t] > goal.max_very_hard]
    by_index = bool(over_index) or (goal.max_index is not None and not over_hard)
    value = max(index.values(), default=0.0) if by_index else float(max(hard.values(), default=0))
    limit = goal.max_index if by_index else float(goal.max_very_hard or 0)
    over = sorted(set(over_index + over_hard), key=term_key)
    what = "difficulty index" if by_index else "number of very hard courses"
    return GoalOutcome(
        _result(goal, value, limit, not over),
        message=f"The {what} reaches {value:g} against a cap of {limit:g} ({', '.join(over)}).",
        terms=over,
        hints=[f"Move a hard course out of {t}." for t in over],
        assumptions=_unknown(missing, "difficulty"),
        score=1.0 if not over else _ratio(value, float(limit or 0)),
    )


def _challenge(goal: ChallengeGoal, ctx: _Ctx) -> GoalOutcome:
    missing: set[str] = set()
    sums = [
        sum(ctx.attribute(c, "difficulty", missing) for c in ctx.courses(t))
        for t in ctx.terms(goal)
    ]
    value = sum(sums) / len(sums) if sums else 0.0
    ok = value >= goal.min_index
    return GoalOutcome(
        _result(goal, value, goal.min_index, ok),
        message=f"The difficulty index averages {value:.1f} per quarter; the goal is at least "
        f"{goal.min_index:g}.",
        terms=[goal.term] if goal.term else [],
        hints=["Add a more demanding course."],
        assumptions=_unknown(missing, "difficulty"),
        score=1.0 if ok else _ratio(value, goal.min_index),
    )


def _protect_gpa(goal: ProtectGpaGoal, ctx: _Ctx) -> GoalOutcome:
    missing: set[str] = set()
    threshold = (
        goal.strictness_threshold if goal.strictness_threshold is not None else STRICT_GRADING
    )
    strict = {
        t: [
            c.code
            for c in ctx.courses(t)
            if ctx.attribute(c, "grading_strictness", missing) >= threshold
        ]
        for t in ctx.terms(goal)
    }
    over = [t for t, codes in strict.items() if len(codes) > 1]
    value = float(max((len(codes) for codes in strict.values()), default=0))
    return GoalOutcome(
        _result(goal, value, 1.0, not over),
        message=f"{', '.join(over)}: more than one strictly graded course in a quarter.",
        terms=over,
        courses=[code for t in over for code in strict[t]],
        hints=[f"Move one of {', '.join(strict[t])} out of {t}." for t in over],
        assumptions=_unknown(missing, "grading strictness"),
        score=1.0 if not over else _ratio(1.0, value),
    )


def _graduate_by(goal: GraduateByGoal, ctx: _Ctx) -> GoalOutcome:
    target = ctx.deadline(goal.by_term)
    late = [t for t in ctx.facts.terms if term_key(t) > term_key(target)]
    value = float(sum(ctx.facts.course_count(t) for t in late))
    return GoalOutcome(
        _result(goal, value, 0.0, not late),
        message=f"{value:g} course(s) are planned after {target}, the target graduation quarter.",
        terms=late,
        hints=[f"Move the courses in {', '.join(late)} to {target} or earlier."],
        score=1.0 if not late else 0.0,
    )


def _block_keys(program: ProgramRules, ctx: _Ctx) -> Callable[[Taken], bool]:
    selectors = [n.from_ for _, n in iter_nodes(program) if isinstance(n, SelectNode)]
    selectors += [part.from_ for _, part in iter_parts(program)]
    codes = {
        ctx.idx.canon(c)
        for _, n in iter_nodes(program)
        if isinstance(n, SlotNode)
        for c in n.any_of
    }
    return lambda t: t.key in codes or any(ctx.idx.matches(s, t.code) for s in selectors)


def _study_abroad(goal: StudyAbroadGoal, ctx: _Ctx) -> GoalOutcome:
    term = ctx.deadline(goal.abroad_term)
    program = ctx.program(goal.program_id)
    if program is None:
        return GoalOutcome(
            _result(goal, None, 0.0, False),
            message=f"The study-abroad block {goal.program_id} is not one of the plan's programs.",
            hints=[f"Add {goal.program_id} to the plan."],
            score=0.0,
        )
    in_block = _block_keys(program, ctx)
    used = [
        ctx.facts.taken.get(ctx.idx.canon(code))
        for path, codes in sorted(ctx.state.assignments.items())
        if path == program.id or path.startswith(program.id + "/")
        for code in codes
    ]
    placed = program.id in ctx.state.satisfied and all(
        t is not None and t.term == term for t in used
    )
    on_campus = [t.code for t in ctx.courses(term) if not in_block(t)]
    stray = sum(
        p.term == term and not (p.slot_ref or "").startswith(program.id)
        for p in ctx.facts.placeholders
    )
    value = float(len(on_campus) + stray)
    ok = placed and value == 0
    problem = (
        f"{len(on_campus) + stray} on-campus course(s) are planned in {term}"
        if placed
        else f"the block {program.id} is not fully placed in {term}"
    )
    return GoalOutcome(
        _result(goal, value, 0.0, ok),
        message=f"Study abroad in {term}: {problem}.",
        terms=[term],
        courses=on_campus,
        hints=[f"Place the courses of {program.id} in {term} and move other courses out."],
        score=1.0 if ok else 0.0,
    )


def _missing_by(codes: Sequence[str], deadline: str, ctx: _Ctx, strict: bool) -> list[str]:
    return [c for c in codes if ctx.facts.done(c, deadline, strict=strict) is None]


def _needed(courses: list[str], list_name: str | None, ctx: _Ctx) -> list[str]:
    keys = {ctx.idx.canon(c): c for c in courses}
    if list_name is not None:
        for key in ctx.idx.list_members(list_name):
            keys.setdefault(key, key)
    return [keys[k] for k in sorted(keys)]


def _courses_by(
    goal: BxmsGoal | PremedGoal | LanguageGoal,
    needed: list[str],
    deadline: str,
    ctx: _Ctx,
    what: str,
    strict: bool = False,
) -> GoalOutcome:
    missing = _missing_by(needed, deadline, ctx, strict)
    when = "before" if strict else "by"
    return GoalOutcome(
        _result(goal, float(len(missing)), 0.0, not missing),
        message=f"{what}: {', '.join(missing)} not done {when} {deadline}.",
        terms=[deadline],
        courses=missing,
        hints=[f"Schedule {c} {when} {deadline}." for c in missing],
        score=1.0 if not missing else round(1 - len(missing) / len(needed), 2),
    )


def _bxms(goal: BxmsGoal, ctx: _Ctx) -> GoalOutcome:
    program = ctx.program(goal.program_id)
    if program is None:
        return GoalOutcome(
            _result(goal, None, 0.0, False),
            message=f"The program {goal.program_id} is not one of the plan's programs.",
            hints=[f"Add {goal.program_id} to the plan."],
            score=0.0,
        )
    timing = program.policy.timing
    needed = list(timing.apply_requires) if timing is not None else []
    out = _courses_by(
        goal, needed, ctx.deadline(goal.apply_by), ctx, f"{program.id} application", strict=True
    )
    if not needed:
        out.assumptions.append(f"No application prerequisites are encoded for {program.id}.")
    return out


def _premed(goal: PremedGoal, ctx: _Ctx) -> GoalOutcome:
    needed = _needed(goal.courses, goal.list_, ctx)
    return _courses_by(
        goal, needed, ctx.deadline(goal.complete_by), ctx, "Pre-professional courses"
    )


def _language(goal: LanguageGoal, ctx: _Ctx) -> GoalOutcome:
    needed = _needed(goal.courses, goal.list_, ctx)
    if not needed:
        return GoalOutcome(
            _result(goal, None, 0.0, False),
            message=f"The {goal.language} goal names no courses or course list, so it cannot "
            "be checked.",
            hints=["Edit the goal and choose the language sequence."],
            score=0.0,
        )
    what = f"{goal.language} ({goal.level})"
    return _courses_by(goal, needed, ctx.deadline(goal.by_term), ctx, what)


def _interest(goal: InterestGoal, ctx: _Ctx) -> GoalOutcome:
    slots = {
        path
        for program in ctx.rules.programs
        for path, node in iter_nodes(program)
        if isinstance(node, SlotNode)
    }
    fixed = {
        ctx.idx.canon(code)
        for path, codes in ctx.state.assignments.items()
        if path in slots
        for code in codes
    }
    electives = [t for t in ctx.facts.taken.values() if t.term is not None and t.key not in fixed]
    tagged = [t for t in electives if ctx.idx.tags(t.code) & set(goal.tags)]
    share = len(tagged) / len(electives) if electives else 0.0
    ok = goal.min_share is None or share >= goal.min_share
    return GoalOutcome(
        _result(goal, share, goal.min_share, ok),
        message=f"{share:.0%} of electives are tagged {', '.join(goal.tags)}; the goal is "
        f"{(goal.min_share or 0):.0%}.",
        hints=[f"Choose more electives tagged {', '.join(goal.tags)}."],
        score=1.0 if ok else _ratio(share, goal.min_share or 0.0),
    )


def _light_quarter(goal: LightQuarterGoal, ctx: _Ctx) -> GoalOutcome:
    assert goal.term is not None
    count = ctx.facts.course_count(goal.term)
    ok = count <= goal.max_courses
    return GoalOutcome(
        _result(goal, float(count), float(goal.max_courses), ok),
        message=f"{goal.term} has {count} courses; the goal is at most {goal.max_courses}.",
        terms=[goal.term],
        hints=[f"Move {count - goal.max_courses} course(s) out of {goal.term}."],
        score=1.0 if ok else _ratio(float(goal.max_courses), float(count)),
    )


_PREDICATES: dict[str, Callable[..., GoalOutcome]] = {
    "course_load": _course_load,
    "workload_hours": _workload,
    "difficulty_cap": _difficulty_cap,
    "challenge": _challenge,
    "protect_gpa": _protect_gpa,
    "graduate_by": _graduate_by,
    "study_abroad": _study_abroad,
    "bxms": _bxms,
    "premed": _premed,
    "interest": _interest,
    "light_quarter": _light_quarter,
    "language": _language,
}


def evaluate_goals(
    facts: PlanFacts, idx: Index, rules: RuleSet, state: ProgramState, *, strict: bool = False
) -> list[GoalOutcome]:
    """One outcome per goal, in plan order. `strict` makes workload goals use the upper
    confidence bound (VerifyOptions.strictness)."""
    ctx = _Ctx(facts=facts, idx=idx, rules=rules, state=state, strict=strict)
    return [_PREDICATES[goal.type](goal, ctx) for goal in facts.plan.goals]
