"""Builds the certificate from what the checks computed (SPEC "Certificates and the trusted
checker"). The builder only copies results; `planner_core.certificate` re-derives them."""

from __future__ import annotations

from planner_core.goals import GoalOutcome
from planner_core.hashing import plan_hash, program_key, rules_hash
from planner_core.index import PlanFacts
from planner_core.models import (
    Assignment,
    Certificate,
    LoadEntry,
    PlanState,
    PrereqWitness,
    ProgramRules,
)
from planner_core.programs import ProgramsResult
from planner_core.terms import term_key


def build_certificate(
    plan: PlanState,
    programs: list[ProgramRules],
    result: ProgramsResult,
    witnesses: list[PrereqWitness],
    facts: PlanFacts,
    outcomes: list[GoalOutcome],
) -> Certificate:
    return Certificate(
        plan_hash=plan_hash(plan),
        rules={program_key(p): rules_hash(p) for p in programs},
        assignments=[
            Assignment(node=path, courses=codes)
            for path, codes in sorted(result.assignments().items())
        ],
        prereq_witnesses=sorted(witnesses, key=lambda w: (term_key(w.term), w.course)),
        loads=[LoadEntry(term=term, units=facts.loads[term]) for term in facts.terms],
        goals=[outcome.result for outcome in outcomes],
    )
