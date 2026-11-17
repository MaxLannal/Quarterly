"""Goal compiler: each goal becomes a hard bound, a reward or a penalty for the plan
generator, exactly as the "Used by the generator as" column of SPEC "Goal predicates" says.

| Goal type | Used as |
| --- | --- |
| course_load, graduate_by, light_quarter | hard bound |
| workload_hours, difficulty_cap | hard bound when the goal is hard, else a penalty |
| challenge, interest | reward |
| protect_gpa | penalty |
| study_abroad | pinned block |
| bxms, premed, language | precedence constraint |

Terms are resolved against the plan (`Y3-WI` -> `2028-WI`). Labels are plain English, for
the explanation of an impossible request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from planner_core.goals import STRICT_GRADING, VERY_HARD
from planner_core.index import Index
from planner_core.models import (
    BxmsGoal,
    ChallengeGoal,
    CourseLoadGoal,
    DifficultyCapGoal,
    Goal,
    GraduateByGoal,
    InterestGoal,
    LanguageGoal,
    LightQuarterGoal,
    PlanState,
    PremedGoal,
    ProtectGpaGoal,
    RuleSet,
    StudyAbroadGoal,
    WorkloadHoursGoal,
)
from planner_core.terms import parse_term, resolve_term_ref

Mode = Literal["hard", "reward", "penalty", "pin", "precedence"]
_QUARTER = {"AU": "Autumn", "WI": "Winter", "SP": "Spring", "SU": "Summer"}


def term_label(term: str) -> str:
    """`2029-SP` -> "Spring 2029"."""
    year, quarter = parse_term(term)
    return f"{_QUARTER[quarter]} {year}"


@dataclass(frozen=True)
class GoalSpec:
    goal_id: str
    type: str
    mode: Mode
    weight: float
    label: str
    #: Terms a per-term goal applies to; empty = every term of the plan.
    terms: tuple[str, ...] = ()
    #: Upper bound (courses, hours, difficulty index or count of very hard courses).
    limit: float | None = None
    #: Lower bound (courses per term, or the challenge index).
    floor: float | None = None
    #: Courses a precedence goal needs, and the term they must be done by.
    courses: tuple[str, ...] = ()
    deadline: str | None = None
    #: The deadline is strict (done before it, not in it): `bxms` apply_by.
    strict_deadline: bool = False
    program_id: str | None = None
    tags: tuple[str, ...] = ()
    #: Difficulty / grading-strictness threshold for "very hard" / "strict grading".
    threshold: float | None = None
    #: "per_term" or "career_average" (workload_hours).
    aggregate: str = "per_term"
    #: Use the upper confidence bound of attribute values (workload_hours, strict).
    upper: bool = False
    #: Very hard courses allowed per term (difficulty_cap); None = no count cap.
    max_very_hard: int | None = None
    notes: list[str] = field(default_factory=list)


def _list_codes(idx: Index, name: str | None) -> list[str]:
    return sorted(idx.list_members(name)) if name is not None else []


def compile_goals(goals: list[Goal], plan: PlanState, rules: RuleSet, idx: Index) -> list[GoalSpec]:
    entry = plan.entry_term
    specs: list[GoalSpec] = []
    for goal in goals:
        terms = (goal.term,) if goal.term is not None else ()
        where = f" in {term_label(goal.term)}" if goal.term is not None else ""
        if isinstance(goal, CourseLoadGoal):
            span = (
                f"{goal.min_courses}-{goal.max_courses}"
                if goal.min_courses is not None and goal.max_courses is not None
                else f"at most {goal.max_courses}"
                if goal.max_courses is not None
                else f"at least {goal.min_courses}"
            )
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "hard",
                    goal.weight,
                    f"Taking {span} courses per quarter{where}",
                    terms=terms,
                    limit=goal.max_courses,
                    floor=goal.min_courses,
                )
            )
        elif isinstance(goal, LightQuarterGoal):
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "hard",
                    goal.weight,
                    f"Keeping {term_label(goal.term or entry)} to {goal.max_courses} courses",
                    terms=terms,
                    limit=goal.max_courses,
                )
            )
        elif isinstance(goal, GraduateByGoal):
            deadline = resolve_term_ref(goal.by_term, entry)
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "hard",
                    goal.weight,
                    f"Graduating by {term_label(deadline)}",
                    deadline=deadline,
                )
            )
        elif isinstance(goal, WorkloadHoursGoal):
            per = "a quarter" if goal.aggregate == "per_term" else "a quarter on average"
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "hard" if goal.hard else "penalty",
                    goal.weight,
                    f"At most {goal.max_hours:g} hours of work a week in {per}{where}",
                    terms=terms,
                    limit=goal.max_hours,
                    aggregate=goal.aggregate,
                    upper=goal.strict,
                )
            )
        elif isinstance(goal, DifficultyCapGoal):
            what = (
                f"at most {goal.max_very_hard} very hard course(s) per quarter"
                if goal.max_very_hard is not None
                else f"a difficulty index of at most {goal.max_index:g} per quarter"
            )
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "hard" if goal.hard else "penalty",
                    goal.weight,
                    f"Taking {what}{where}",
                    terms=terms,
                    limit=goal.max_index,
                    threshold=goal.very_hard_threshold or VERY_HARD,
                    max_very_hard=goal.max_very_hard,
                )
            )
        elif isinstance(goal, ChallengeGoal):
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "reward",
                    goal.weight,
                    "Challenging courses",
                    terms=terms,
                    floor=goal.min_index,
                )
            )
        elif isinstance(goal, ProtectGpaGoal):
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "penalty",
                    goal.weight,
                    "No two strictly graded courses in one quarter",
                    terms=terms,
                    threshold=goal.strictness_threshold or STRICT_GRADING,
                )
            )
        elif isinstance(goal, InterestGoal):
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "reward",
                    goal.weight,
                    f"Courses about {', '.join(goal.tags)}",
                    tags=tuple(goal.tags),
                )
            )
        elif isinstance(goal, StudyAbroadGoal):
            term = resolve_term_ref(goal.abroad_term, entry)
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "pin",
                    goal.weight,
                    f"Spending {term_label(term)} abroad ({goal.program_id})",
                    terms=(term,),
                    program_id=goal.program_id,
                )
            )
        elif isinstance(goal, BxmsGoal):
            deadline = resolve_term_ref(goal.apply_by, entry)
            program = next((p for p in rules.programs if p.id == goal.program_id), None)
            timing = program.policy.timing if program is not None else None
            courses = tuple(timing.apply_requires) if timing is not None else ()
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "precedence",
                    goal.weight,
                    f"Being ready to apply to {goal.program_id} by {term_label(deadline)}",
                    courses=courses,
                    deadline=deadline,
                    strict_deadline=True,
                    program_id=goal.program_id,
                )
            )
        elif isinstance(goal, PremedGoal | LanguageGoal):
            by = goal.complete_by if isinstance(goal, PremedGoal) else goal.by_term
            deadline = resolve_term_ref(by, entry)
            courses = tuple(dict.fromkeys([*goal.courses, *_list_codes(idx, goal.list_)]))
            what = "the pre-med courses" if isinstance(goal, PremedGoal) else f"{goal.language}"
            specs.append(
                GoalSpec(
                    goal.id,
                    goal.type,
                    "precedence",
                    goal.weight,
                    f"Finishing {what} by {term_label(deadline)}",
                    courses=courses,
                    deadline=deadline,
                )
            )
    return specs
