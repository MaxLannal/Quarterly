"""Checks V01-V06 and V09-V11: pure functions from plan facts to `Issue` lists.

V07, V08 and V12 need the solver and live in `planner_core.programs`. The exact reading of
each rule is written up in docs/CONTRACTS.md ("Verifier semantics"); the short version sits
in each function's docstring.
"""

from __future__ import annotations

from planner_core.dsl import expr_to_text, node_paths
from planner_core.goals import GoalOutcome
from planner_core.index import ENROLLED, Index, PlanFacts, Taken
from planner_core.models import (
    Atom,
    Catalog,
    CollegePolicy,
    Issue,
    NodeProgress,
    OverloadReason,
    PlanState,
    PrereqWitness,
    RuleSet,
    Section,
    StudyAbroadGoal,
)
from planner_core.prereqs import Evaluation, evaluate
from planner_core.programs import ProgramsResult, late_courses, plan_programs
from planner_core.terms import parse_term, resolve_term_ref, term_key, year_index

#: SPEC "Predicting future offerings": warn when a course is placed where p_offered < 0.3.
P_OFFERED_WARN = 0.3
_QUARTER_NAMES = {"AU": "Autumn", "WI": "Winter", "SP": "Spring", "SU": "Summer"}
NO_COLLEGE_POLICY = (
    "No College policy is loaded for this catalog year, so quarter loads (V05), graduation "
    "totals (V09) and Core timing (V10) were not checked."
)


def _error(code: str, message: str, **fields: object) -> Issue:
    return Issue.model_validate({"code": code, "level": "error", "message": message, **fields})


def _warning(code: str, message: str, **fields: object) -> Issue:
    return Issue.model_validate({"code": code, "level": "warning", "message": message, **fields})


# --------------------------------------------------------------------------------------------
# V01 existence
# --------------------------------------------------------------------------------------------


def check_v01(
    plan: PlanState, rules: RuleSet, catalog: Catalog, facts: PlanFacts, idx: Index
) -> list[Issue]:
    """Every course, credit target, program and placeholder exists in the plan's catalog
    year. Cross-listed codes collapse to one course (see `Index.canon`)."""
    issues: list[Issue] = []
    year = plan.catalog_year
    for name, other in (("rules", rules.catalog_year), ("catalog", catalog.catalog_year)):
        if other != year:
            issues.append(
                _error(
                    "V01", f"The plan is for catalog year {year} but the {name} are for {other}."
                )
            )
    unknown: dict[str, list[str]] = {}
    for taken in facts.items:
        if not idx.known(taken.code) and taken.term is not None:
            unknown.setdefault(taken.code, []).append(taken.term)
    for code, terms in unknown.items():
        issues.append(
            _error(
                "V01",
                f"{code} is not in the {year} catalog.",
                course_ids=[code],
                term_ids=sorted(set(terms), key=term_key),
                fix_hints=[f"Remove {code} or replace it with a course from the {year} catalog."],
            )
        )
    for credit in facts.credits:
        if not idx.known(credit.code):
            issues.append(
                _error(
                    "V01",
                    f"A credit maps to {credit.code}, which is not in the {year} catalog.",
                    course_ids=[credit.code],
                    fix_hints=["Edit the credit so that it maps to a catalog course."],
                )
            )
    loaded = {p.id for p in rules.programs}
    for entry in plan.programs:
        if entry.program_id not in loaded:
            issues.append(
                _error(
                    "V01",
                    f"The program {entry.program_id} has no rules for catalog year {year}, so "
                    "it cannot be checked.",
                    node_id=entry.program_id,
                    fix_hints=[f"Remove {entry.program_id} or choose a program offered in {year}."],
                )
            )
    paths = {path for program in plan_programs(plan, rules) for path in node_paths(program)}
    for item in facts.placeholders:
        if item.slot_ref not in paths:
            issues.append(
                _error(
                    "V01",
                    f"The placeholder in {item.term} points at {item.slot_ref}, which is not a "
                    "requirement of the plan's programs.",
                    term_ids=[item.term],
                    node_id=item.slot_ref,
                    fix_hints=["Remove the placeholder or replace it with a course."],
                )
            )
    return issues


# --------------------------------------------------------------------------------------------
# V02 duplicates and exclusions
# --------------------------------------------------------------------------------------------


def _is_exam(taken: Taken) -> bool:
    return taken.status in ("credit", "exam")


def _where(taken: Taken) -> str:
    return f"{taken.code} ({taken.term})" if taken.term is not None else f"{taken.code} (credit)"


def check_v02(facts: PlanFacts, idx: Index) -> list[Issue]:
    """No course twice unless repeatable (cross-listed codes are one course); no two courses
    related as mutually exclusive, equivalent or replacing; exam or placement credit is
    forfeited when the course, or its equivalent, is also taken."""
    issues: list[Issue] = []
    by_key: dict[str, list[Taken]] = {}
    for taken in [*facts.credits, *facts.items]:
        if idx.known(taken.code):
            by_key.setdefault(taken.key, []).append(taken)
    for records in by_key.values():
        course = idx.course(records[0].code)
        if len(records) < 2:
            continue
        codes = sorted({t.code for t in records})
        terms = sorted({t.term for t in records if t.term is not None}, key=term_key)
        listed = ", ".join(_where(t) for t in records)
        if any(_is_exam(t) for t in records):
            message = (
                f"Credit for {codes[0]} is forfeited because the course is also taken: {listed}."
            )
            hints = ["Remove the credit, or remove the course and keep the credit."]
        elif course is not None and course.repeatable:
            continue
        elif len(codes) > 1:
            message = f"{' and '.join(codes)} are cross-listed, so they are one course: {listed}."
            hints = ["Keep only one of the cross-listed codes."]
        else:
            message = f"{codes[0]} appears more than once and is not repeatable: {listed}."
            hints = [f"Keep {codes[0]} in one quarter only."]
        issues.append(_error("V02", message, course_ids=codes, term_ids=terms, fix_hints=hints))
    seen: set[tuple[str, str]] = set()
    for a, b, kind in idx.relations:
        pair = (min(a, b), max(a, b))
        if a == b or pair in seen or a not in facts.taken or b not in facts.taken:
            continue
        seen.add(pair)
        first, second = facts.taken[a], facts.taken[b]
        if kind == "mutually_exclusive":
            message = (
                f"{first.code} and {second.code} are mutually exclusive: credit is given "
                "for only one."
            )
        elif _is_exam(first) or _is_exam(second):
            message = (
                f"Credit for {first.code} / {second.code} is forfeited because the equivalent "
                "course is also taken."
            )
        else:
            message = (
                f"{first.code} and {second.code} are equivalent courses: credit is given "
                "for only one."
            )
        issues.append(
            _error(
                "V02",
                message,
                course_ids=sorted([first.code, second.code]),
                term_ids=sorted({t.term for t in (first, second) if t.term}, key=term_key),
                fix_hints=[f"Remove {first.code} or {second.code}."],
            )
        )
    return issues


# --------------------------------------------------------------------------------------------
# V03 prerequisites
# --------------------------------------------------------------------------------------------


def _missing_text(atom: Atom, item: Taken, facts: PlanFacts) -> tuple[str, str]:
    """(what is wrong, how to fix it) for one unmet atom."""
    term = item.term
    if atom.kind in ("course", "concurrent"):
        when = "before" if atom.kind == "course" else "in or before"
        have = facts.done(atom.value)
        grade = f" with grade {atom.min_grade} or higher" if atom.min_grade else ""
        if have is None:
            return (
                f"{atom.value}{grade} is not in the plan",
                f"Add {atom.value} {when} {term}.",
            )
        if have.term is not None and have.order >= item.order and have.key != item.key:
            return (
                f"{have.code} is in {have.term}, which is not {when} {term}",
                f"Move {have.code} {when} {term}, or move {item.code} later.",
            )
        return (
            f"{have.code} has grade {have.grade}, below the required {atom.min_grade}",
            f"Retake {have.code} or ask the department about the grade requirement.",
        )
    if atom.kind == "placement":
        return (f"placement into {atom.value} is not recorded", "Add the placement to the plan.")
    if atom.kind == "standing":
        return (
            f"{atom.value} standing is needed in {term}",
            f"Move {item.code} to a quarter in which you have {atom.value} standing.",
        )
    return (
        f"enrolment is restricted to students in {atom.value}",
        f"Add the program {atom.value} to the plan or remove {item.code}.",
    )


def check_v03(facts: PlanFacts, idx: Index) -> tuple[list[Issue], list[PrereqWitness], bool]:
    """Prerequisites, co-requisites and restrictions of every planned or in-progress course
    (completed, transfer and exam items are history and are not re-checked). Returns the
    issues, one witness per checked course that has a requisite, and whether any ungraded
    course was assumed to meet a grade minimum."""
    issues: list[Issue] = []
    witnesses: list[PrereqWitness] = []
    assumed = False
    for item in facts.items:
        if item.status not in ("planned", "in_progress") or not idx.known(item.code):
            continue
        requisite = idx.requisite(item.code)
        assert item.term is not None
        if requisite is None:
            continue
        parts = [
            (requisite.prereq, False, "Prerequisite"),
            (requisite.coreq, True, "Co-requisite"),
            (requisite.restrictions, False, "Restriction"),
        ]
        results: list[Evaluation] = []
        for expr, coreq, name in parts:
            if expr is None:
                continue
            result = evaluate(expr, item, facts, coreq=coreq)
            results.append(result)
            if result.ok:
                continue
            texts = [_missing_text(atom, item, facts) for atom in result.missing]
            issues.append(
                _error(
                    "V03",
                    f"{name} of {item.code} in {item.term} is not met: "
                    f"{'; '.join(dict.fromkeys(t[0] for t in texts))}. "
                    f"Requirement: {expr_to_text(expr)}.",
                    course_ids=[item.code],
                    term_ids=[item.term],
                    fix_hints=list(dict.fromkeys(t[1] for t in texts)),
                )
            )
        if not results:
            continue
        assumed = assumed or any(r.assumed_grade for r in results if r.ok)
        for value in dict.fromkeys(v for r in results if r.ok for v in r.consents):
            issues.append(
                _warning(
                    "V03",
                    f"{item.code} in {item.term} needs the consent of the {value}.",
                    course_ids=[item.code],
                    term_ids=[item.term],
                    fix_hints=[f"Ask for the {value}'s consent before registering."],
                )
            )
        if all(r.ok for r in results):
            by = list(dict.fromkeys(token for r in results for token in r.by))
            witnesses.append(PrereqWitness(course=item.code, term=item.term, by=by))
    return issues, witnesses, assumed


# --------------------------------------------------------------------------------------------
# V04 offerings
# --------------------------------------------------------------------------------------------


def check_v04(facts: PlanFacts, idx: Index) -> list[Issue]:
    """Planned courses only. A posted schedule wins: no section in a posted term is an error.
    Otherwise a predicted `p_offered` below 0.3 is a warning; a course with no offering
    pattern at all is not flagged."""
    issues: list[Issue] = []
    for item in facts.items:
        if item.status != "planned" or item.term is None or not idx.known(item.code):
            continue
        quarter = parse_term(item.term)[1]
        if item.term in idx.posted_terms:
            if not idx.sections(item.term, item.code):
                issues.append(
                    _error(
                        "V04",
                        f"{item.code} is not on the posted schedule for {item.term}.",
                        course_ids=[item.code],
                        term_ids=[item.term],
                        fix_hints=[f"Move {item.code} to a quarter in which it is offered."],
                    )
                )
            continue
        p = idx.p_offered(item.code, quarter)
        if p is not None and p < P_OFFERED_WARN:
            better = [
                _QUARTER_NAMES[q]
                for q in ("AU", "WI", "SP", "SU")
                if (idx.p_offered(item.code, q) or 0.0) >= P_OFFERED_WARN
            ]
            hint = (
                f"Move {item.code} to {' or '.join(better)}."
                if better
                else f"Check with the department when {item.code} will be offered."
            )
            issues.append(
                _warning(
                    "V04",
                    f"{item.code} is not usually offered in {_QUARTER_NAMES[quarter]} "
                    f"(estimated chance {p:.0%}).",
                    course_ids=[item.code],
                    term_ids=[item.term],
                    fix_hints=[hint],
                )
            )
    return issues


# --------------------------------------------------------------------------------------------
# V05 quarter loads
# --------------------------------------------------------------------------------------------


def reason_applies(reason: OverloadReason, term: str, facts: PlanFacts, idx: Index) -> bool:
    courses = facts.by_term.get(term, [])
    if reason.year is not None and facts.class_year(term) != reason.year:
        return False
    if reason.course_selector is not None and not any(
        idx.matches(reason.course_selector, t.code) for t in courses
    ):
        return False
    return reason.min_course_units is None or any(
        t.units >= reason.min_course_units for t in courses
    )


def check_v05(facts: PlanFacts, idx: Index, college: CollegePolicy) -> list[Issue]:
    """Autumn, Winter and Spring quarters that have at least one course must carry the
    full-time load. Above the maximum, up to `overload_units`, a claimed overload reason whose
    conditions hold gives a "needs petition" warning; anything else is an error. Empty
    quarters and Summer are not checked. A quarter whose courses are all completed is history:
    its load is reported as info, since it cannot be changed."""
    issues: list[Issue] = []
    low, high, cap = (
        college.full_time_min_units,
        college.full_time_max_units,
        college.overload_units,
    )
    reasons = {r.id: r for r in college.overload_reasons}
    for term in facts.terms:
        if parse_term(term)[1] == "SU":
            continue
        units = facts.loads[term]
        courses = facts.by_term.get(term, [])
        history = bool(courses) and all(t.status == "completed" for t in courses)
        history = history and not any(p.term == term for p in facts.placeholders)
        level = "info" if history else "error"
        if low is not None and units < low:
            issues.append(
                Issue(
                    code="V05",
                    level=level,
                    message=f"{term} has {units} units; a full-time quarter needs at least {low}.",
                    term_ids=[term],
                    fix_hints=[
                        f"Add {low - units} more units to {term}, or leave it empty for now."
                    ],
                )
            )
        elif high is not None and units > high:
            claimed = facts.plan.overload_reasons.get(term)
            reason = reasons.get(claimed) if claimed is not None else None
            usable = [r for r in reasons.values() if reason_applies(r, term, facts, idx)]
            within = cap is not None and units <= cap
            if within and reason is not None and reason in usable:
                issues.append(
                    _warning(
                        "V05",
                        f"{term} has {units} units: this overload needs a petition "
                        f"({reason.label}).",
                        term_ids=[term],
                        fix_hints=["Petition your College adviser for the overload."],
                    )
                )
                continue
            if not within:
                why = f"the most a quarter can carry is {cap if cap is not None else high}"
            elif reason is None:
                why = f"more than {high} units needs an overload reason"
            else:
                why = f"the overload reason '{reason.label}' does not apply to this quarter"
            hints = [f"Move a course out of {term}."]
            if within:
                hints += [f"Claim the overload reason '{r.label}' ({r.id})." for r in usable]
            issues.append(
                Issue(
                    code="V05",
                    level=level,
                    message=f"{term} has {units} units; {why}.",
                    term_ids=[term],
                    fix_hints=hints,
                )
            )
    return issues


# --------------------------------------------------------------------------------------------
# V06 meeting-time clashes
# --------------------------------------------------------------------------------------------


def _overlap(a: Section, b: Section) -> bool:
    return any(
        set(ma.days) & set(mb.days) and ma.start < mb.end and mb.start < ma.end
        for ma in a.meetings
        for mb in b.meetings
    )


def _components(sections: list[Section]) -> list[list[Section]]:
    groups: dict[str, list[Section]] = {}
    for section in sections:
        groups.setdefault(section.component or "", []).append(section)
    return list(groups.values())


def check_v06(facts: PlanFacts, idx: Index) -> list[Issue]:
    """For terms with posted sections: two courses clash when, for some component of each
    (lecture, lab, ...), every section of one overlaps every section of the other. A course
    needs one section of each component, so such a pair cannot be scheduled together."""
    issues: list[Issue] = []
    for term in facts.terms:
        if term not in idx.posted_terms:
            continue
        offered = [(t, idx.sections(term, t.code)) for t in facts.by_term.get(term, [])]
        offered = [(t, sections) for t, sections in offered if sections]
        for i, (a, sections_a) in enumerate(offered):
            for b, sections_b in offered[i + 1 :]:
                if a.key != b.key and any(
                    all(_overlap(x, y) for x in group_a for y in group_b)
                    for group_a in _components(sections_a)
                    for group_b in _components(sections_b)
                ):
                    issues.append(
                        _warning(
                            "V06",
                            f"{a.code} and {b.code} meet at the same time in {term}.",
                            course_ids=[a.code, b.code],
                            term_ids=[term],
                            fix_hints=[f"Move {a.code} or {b.code} to another quarter."],
                        )
                    )
    return issues


# --------------------------------------------------------------------------------------------
# V09 graduation
# --------------------------------------------------------------------------------------------


def unit_totals(facts: PlanFacts) -> tuple[int, int]:
    """(total units, units by enrollment). Total counts every course item, placeholder and
    credit; "by enrollment" leaves out transfer and exam items and credits."""
    placeholders = sum(facts.loads.values()) - sum(
        t.units for courses in facts.by_term.values() for t in courses
    )
    enrolled = sum(t.units for t in facts.items if t.status in ENROLLED) + placeholders
    other = sum(t.units for t in facts.items if t.status not in ENROLLED)
    return enrolled + other + sum(c.units for c in facts.plan.credits), enrolled


def check_v09(
    facts: PlanFacts, college: CollegePolicy, result: ProgramsResult
) -> tuple[list[Issue], list[NodeProgress], list[str]]:
    """Graduation: total units, units by enrollment, the Core and Language Competence, the
    residency share of each program, and the number of quarters. Returns issues, progress
    rows under the pseudo-program `college`, and assumptions for values not encoded. On a
    partial plan these are errors by design; the messages say how far the plan is."""
    issues: list[Issue] = []
    progress: list[NodeProgress] = []
    assumptions: list[str] = []
    total, enrolled = unit_totals(facts)
    for field, have, label, what in (
        ("total_units", total, "Units toward the degree", "units in total"),
        ("units_by_enrollment", enrolled, "Units by enrollment", "units earned by enrollment"),
    ):
        need = getattr(college, field)
        if need is None:
            assumptions.append(f"The College policy does not encode {field}; it was not checked.")
            continue
        progress.append(
            NodeProgress(
                program_id="college",
                node_id=f"college/{field}",
                label=label,
                satisfied=have >= need,
                have=have,
                need=need,
                unit="units",
            )
        )
        if have < need:
            issues.append(
                _error(
                    "V09",
                    f"Graduation needs {need} {what}; this plan has {have} so far "
                    f"({need - have} to go).",
                    node_id=f"college/{field}",
                    fix_hints=[f"Add {need - have} more units of courses taken at the College."],
                )
            )
    core = college.core_program_id
    if core not in {p.program_id for p in facts.plan.programs}:
        issues.append(
            _error(
                "V09",
                f"The plan does not include the Core ({core}), so general education cannot be "
                "checked.",
                node_id=core,
                fix_hints=[f"Add the program {core} to the plan."],
            )
        )
    elif core in result.compiled:
        if not result.satisfied(core):
            issues.append(
                _error(
                    "V09",
                    "The Core is not complete; see the missing requirements listed for it.",
                    node_id=core,
                    fix_hints=["Add the missing Core courses."],
                )
            )
        language = college.language_node
        if language is None:
            assumptions.append(
                "The College policy does not name the Language Competence requirement; it was "
                "checked only as part of the Core."
            )
        elif not result.solution.satisfied.get(language, False):
            issues.append(
                _error(
                    "V09",
                    "The Language Competence requirement is not complete.",
                    node_id=language,
                    fix_hints=["Add the language courses or the placement credit that meets it."],
                )
            )
    for program_id, ok in result.solution.residency_ok.items():
        if not ok:
            issues.append(
                _error(
                    "V09",
                    f"Too few courses of {program_id} are taken in residence; transfer and "
                    "exam credit can cover only part of a program.",
                    node_id=program_id,
                    fix_hints=[f"Take more of the {program_id} courses at the College."],
                )
            )
    if college.residency_min_fraction is None:
        assumptions.append(
            "The College policy does not encode the residency share; it was checked only for "
            "programs that state their own."
        )
    if college.max_quarters is None:
        assumptions.append("The College policy does not encode max_quarters; it was not checked.")
    else:
        quarters = [t for t in facts.terms if parse_term(t)[1] != "SU" and facts.by_term.get(t)]
        if len(quarters) > college.max_quarters:
            issues.append(
                _error(
                    "V09",
                    f"The plan uses {len(quarters)} quarters; the College allows "
                    f"{college.max_quarters}.",
                    term_ids=quarters[college.max_quarters :],
                    fix_hints=["Fit the remaining courses into earlier quarters."],
                )
            )
    return issues, progress, assumptions


# --------------------------------------------------------------------------------------------
# V10 timing
# --------------------------------------------------------------------------------------------


def check_v10(
    facts: PlanFacts,
    idx: Index,
    rules: RuleSet,
    result: ProgramsResult,
    time_limit_s: float,
) -> list[Issue]:
    """Warnings. (1) The Core is finished by `core_complete_by`; a Core course taken later
    still counts on time when it is in or before plan year `civ_abroad_year` and belongs to a
    study-abroad block of the plan or sits in the term of a study-abroad goal. (2) A program's
    `complete_by`. (3) A program's `apply_requires` courses are done before `apply_by`."""
    issues: list[Issue] = []
    plan, college = facts.plan, rules.college
    entry = plan.entry_term
    deadlines: list[tuple[str, str, bool]] = []  # (program id, deadline, core exemption)
    if college is not None and college.core_complete_by is not None:
        deadlines.append(
            (college.core_program_id, resolve_term_ref(college.core_complete_by, entry), True)
        )
    for program in result.compiled.values():
        timing = program.program.policy.timing
        if timing is not None and timing.complete_by is not None:
            deadlines.append(
                (program.program.id, resolve_term_ref(timing.complete_by, entry), False)
            )
        if timing is not None and timing.apply_by is not None:
            apply_by = resolve_term_ref(timing.apply_by, entry)
            late = [
                c for c in timing.apply_requires if facts.done(c, apply_by, strict=True) is None
            ]
            if late:
                issues.append(
                    _warning(
                        "V10",
                        f"{program.program.id}: {', '.join(late)} must be complete before the "
                        f"application deadline {apply_by}.",
                        course_ids=late,
                        term_ids=[apply_by],
                        node_id=program.program.id,
                        fix_hints=[f"Schedule {c} before {apply_by}." for c in late],
                    )
                )
    abroad_terms = {
        resolve_term_ref(g.abroad_term, entry) for g in plan.goals if isinstance(g, StudyAbroadGoal)
    }
    abroad_keys = {
        key
        for c in result.compiled.values()
        if c.program.type == "study_abroad_block"
        for key in result.solution.used(c)
    }
    for program_id, deadline, core in deadlines:
        if program_id not in result.compiled:
            continue
        last_year = college.civ_abroad_year if core and college is not None else None

        def on_time(t: Taken, deadline: str = deadline, last_year: int | None = last_year) -> bool:
            if t.term is None or term_key(t.term) <= term_key(deadline):
                return True
            abroad = t.term in abroad_terms or t.key in abroad_keys
            return last_year is not None and abroad and year_index(t.term, entry) <= last_year

        late_used = late_courses(result, program_id, on_time, facts, idx, college, time_limit_s)
        if late_used is None:
            continue
        codes = [t.code for t in late_used]
        detail = f"{', '.join(codes)} come later" if codes else "it is not complete in this plan"
        issues.append(
            _warning(
                "V10",
                f"{program_id} should be finished by {deadline}, but {detail}.",
                course_ids=codes,
                term_ids=[deadline],
                node_id=program_id,
                fix_hints=[f"Move {c} to {deadline} or earlier." for c in codes]
                or [f"Plan the remaining {program_id} requirements by {deadline}."],
            )
        )
    return issues


# --------------------------------------------------------------------------------------------
# V11 goals
# --------------------------------------------------------------------------------------------


def check_v11(plan: PlanState, outcomes: list[GoalOutcome]) -> list[Issue]:
    """A failed hard goal is an error; a failed soft goal is a warning that carries a score
    between 0 and 1 (1 = met)."""
    issues: list[Issue] = []
    for goal, outcome in zip(plan.goals, outcomes, strict=True):
        if outcome.result.pass_:
            continue
        message = outcome.message
        if not goal.hard:
            message += f" (soft goal, score {outcome.score:.2f})"
        issues.append(
            Issue(
                code="V11",
                level="error" if goal.hard else "warning",
                message=message,
                course_ids=outcome.courses,
                term_ids=outcome.terms,
                goal_id=goal.id,
                fix_hints=outcome.hints,
            )
        )
    return issues
