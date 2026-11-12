"""Entry point of the verifier: `verify(plan, rules, catalog, options) -> Report`.

Pure and deterministic: no I/O, no clock, no randomness, a single-threaded solver.

What `verify` settles (details in docs/CONTRACTS.md "Verifier semantics"):
- Only the programs the plan lists are checked; a listed program without rules is a V01 error.
- `options.checks` runs only the named checks. V08 and V12 are part of the V07 model, so a
  plan that passes V07 has no V08 or V12 error.
- `Report.status` is "errors" if any issue is an error, else "warnings" if any is a warning,
  else "valid". Info issues never change the status.
- A certificate is attached only when it can be complete: no reported errors, prerequisites
  and program requirements hold (they are evaluated for the certificate even when
  `options.checks` leaves V03 or V07 out), every listed program has rules and every hard goal
  holds. `verify` does not call the checker; callers that show "Valid" use `verify_checked`.
- `Report.progress` and `Report.assumptions` are filled whatever the status, so a partial
  plan still shows how far it is.
"""

from __future__ import annotations

from typing import Literal

from planner_core.certificate import certificate_problems
from planner_core.certify import build_certificate
from planner_core.checks import (
    NO_COLLEGE_POLICY,
    check_v01,
    check_v02,
    check_v03,
    check_v04,
    check_v05,
    check_v06,
    check_v09,
    check_v10,
    check_v11,
)
from planner_core.goals import GoalOutcome, ProgramState, evaluate_goals
from planner_core.hashing import plan_hash
from planner_core.index import Index, PlanFacts
from planner_core.models import (
    Catalog,
    Issue,
    PlanState,
    PrereqWitness,
    Report,
    RuleSet,
    VerifyOptions,
)
from planner_core.programs import ProgramsResult, check_programs, plan_programs
from planner_core.version import CORE_VERSION

ALL_CHECKS = ("V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08", "V09", "V10", "V11", "V12")
GRADE_ASSUMPTION = "Courses without a recorded grade are assumed to meet grade minimums."

Status = Literal["valid", "warnings", "errors"]


def verify(
    plan: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    options: VerifyOptions | None = None,
) -> Report:
    """Pure function: run checks V01-V12 and, when there are no errors, build a Certificate.

    Contract: deterministic for equal inputs; never performs I/O; `Report.plan_hash` equals
    `planner_core.hashing.plan_hash(plan)`; `Report.status` is "errors" if any issue has level
    "error", else "warnings" if any warning, else "valid"."""
    options = options or VerifyOptions()
    run = set(ALL_CHECKS) if options.checks is None else set(options.checks)
    idx = Index(catalog, rules)
    facts = PlanFacts(plan, idx)
    college = rules.college
    limit = options.solver_time_limit_s
    issues: list[Issue] = []
    assumptions: list[str] = []
    witnesses: list[PrereqWitness] = []

    if "V01" in run:
        issues += check_v01(plan, rules, catalog, facts, idx)
    if "V02" in run:
        issues += check_v02(facts, idx)
    # The certificate attests prerequisites and program satisfaction, so both are evaluated
    # whenever a certificate is wanted; their issues are reported only if the check was asked.
    wanted = options.include_certificate
    prereqs_hold = False
    if "V03" in run or wanted:
        found, witnesses, assumed = check_v03(facts, idx)
        prereqs_hold = not any(issue.level == "error" for issue in found)
        if "V03" in run:
            issues += found
            if assumed:
                assumptions.append(GRADE_ASSUMPTION)
    if "V04" in run:
        issues += check_v04(facts, idx)
    if college is None and run & {"V05", "V09", "V10"}:
        assumptions.append(NO_COLLEGE_POLICY)
    if "V05" in run and college is not None:
        if college.full_time_min_units is None and college.full_time_max_units is None:
            assumptions.append(
                "The College policy does not encode the full-time load; quarter loads were "
                "not checked."
            )
        issues += check_v05(facts, idx, college)
    if "V06" in run:
        issues += check_v06(facts, idx)

    result = ProgramsResult()
    if run & {"V07", "V08", "V09", "V10", "V12"} or plan.goals or wanted:
        result = check_programs(plan, rules, facts, idx, limit)
        assumptions += result.assumptions
        for code, found in (("V07", result.v07), ("V08", result.v08), ("V12", result.v12)):
            if code in run:
                issues += found
        if any(
            unit.min_grade is not None and any(t.grade is None for t in unit.eligible)
            for compiled in result.compiled.values()
            for unit in compiled.units.values()
        ):
            assumptions.append(GRADE_ASSUMPTION)
    progress = list(result.progress)
    if "V09" in run and college is not None:
        found, rows, notes = check_v09(facts, college, result)
        issues += found
        progress += rows
        assumptions += notes
    if "V10" in run:
        issues += check_v10(facts, idx, rules, result, limit)

    state = ProgramState(satisfied=result.satisfied_programs(), assignments=result.assignments())
    outcomes: list[GoalOutcome] = evaluate_goals(
        facts, idx, rules, state, strict=options.strictness == "strict"
    )
    if "V11" in run:
        issues += check_v11(plan, outcomes)
        assumptions += [note for outcome in outcomes for note in outcome.assumptions]

    issues.sort(key=lambda issue: issue.code)  # stable: keeps each check's own order
    status = _status(issues)
    programs = plan_programs(plan, rules)
    certifiable = (
        wanted
        and status != "errors"
        and prereqs_hold
        and not result.v07
        and not result.v08
        and len(programs) == len({p.program_id for p in plan.programs})
        and all(o.result.pass_ for goal, o in zip(plan.goals, outcomes, strict=True) if goal.hard)
    )
    return Report(
        status=status,
        plan_hash=plan_hash(plan),
        core_version=CORE_VERSION,
        issues=issues,
        certificate=(
            build_certificate(plan, programs, result, witnesses, facts, outcomes)
            if certifiable
            else None
        ),
        progress=progress,
        assumptions=list(dict.fromkeys(assumptions)),
    )


def _status(issues: list[Issue]) -> Status:
    levels = {issue.level for issue in issues}
    return "errors" if "error" in levels else "warnings" if "warning" in levels else "valid"


def verify_checked(
    plan: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    options: VerifyOptions | None = None,
) -> tuple[Report, list[str]]:
    """`verify` followed by the trusted checker: the only way to obtain a report that may be
    shown as "Valid" (CLAUDE.md hard rule). Returns the report and the checker's problems.

    - The certificate is rejected: it is dropped, the status becomes "errors", a V07 error
      explains it, and the problems are returned so the caller can raise an alert.
    - No certificate and no reported errors (a restricted `checks` run that hides a failed
      prerequisite or program requirement): the status is downgraded to "warnings" with a
      note, because such a run proves nothing about validity.
    - `include_certificate=False` only hides the certificate; it is still built and checked."""
    options = options or VerifyOptions()
    report = verify(plan, rules, catalog, options.model_copy(update={"include_certificate": True}))
    problems: list[str] = []
    extra: Issue | None = None
    if report.certificate is not None:
        problems = certificate_problems(plan, rules, catalog, report.certificate)
        if problems:
            extra = Issue(
                code="V07",
                level="error",
                message="Internal check failed: the independent checker rejected this plan's "
                "certificate, so the plan cannot be shown as valid.",
                fix_hints=["Try again; if this keeps happening, report it."],
            )
    elif report.status != "errors":
        extra = Issue(
            code="V07",
            level="warning",
            message="Partial check: the plan could not be certified, because prerequisites "
            "(V03) or program requirements (V07, V08) outside the requested checks do not hold.",
            fix_hints=["Run all checks to see what is missing."],
        )
    updates: dict[str, object] = {}
    if extra is not None:
        updates = {"issues": [*report.issues, extra], "status": _status([*report.issues, extra])}
    if problems or not options.include_certificate:
        updates["certificate"] = None
    return (report.model_copy(update=updates) if updates else report), problems
