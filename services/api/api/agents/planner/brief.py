"""The requirements brief: every unmet requirement of the plan's programs, with what counts and
candidate courses with the quarters they are usually offered. Built from Quarterly's compiled
rules and offering data only; nothing here is written by a model (plan-guideline G01, G08).

Ported from `PlanTools.requirements_brief` of ZhihchengGao/degree-plan-agent (issue #17).
"""

from __future__ import annotations

from planner_core.dsl import expr_to_text
from planner_core.index import Index, PlanFacts, describe_selector
from planner_core.models import Catalog, PlanState, Report, RuleSet, Selector
from planner_core.programs import plan_programs
from planner_core.tree import compile_program

#: The same threshold as the verifier's V04 warning ("not usually offered").
OFFERED_MIN = 0.3
CREDIT_ONLY = "credit_only"
QUARTERS = ("AU", "WI", "SP", "SU")


def offered(idx: Index, code: str) -> list[str]:
    out = []
    for q in QUARTERS:
        p = idx.p_offered(code, q)
        if p is not None and p >= OFFERED_MIN:
            out.append(q)
    return out


def offered_text(idx: Index, code: str) -> str:
    qs = offered(idx, code)
    return "/".join(qs) if qs else "no offering data"


PREREQ_CHARS = 90


def prereq_text(idx: Index, code: str) -> str | None:
    """The prerequisite in short words, from the requisite data (never from a model)."""
    req = idx.requisite(code)
    if req is None or req.prereq is None:
        return None
    try:
        text = expr_to_text(req.prereq)
    except Exception:
        text = req.raw_text or ""
    return text[:PREREQ_CHARS] or None


def candidate_text(idx: Index, code: str) -> str:
    """`CODE [quarters]`, then `(needs ...)` when the course has a prerequisite."""
    needs = prereq_text(idx, code)
    return f"{code} [{offered_text(idx, code)}]" + (f" (needs {needs})" if needs else "")


def _tags(idx: Index, code: str) -> list[str]:
    course = idx.course(code)
    return list(course.tags) if course is not None else []


def _candidates(idx: Index, catalog: Catalog, selector: Selector, limit: int) -> list[str]:
    out: list[str] = []
    if selector.codes:
        out = list(selector.codes)
    elif selector.list_:
        out = sorted(idx.list_members(selector.list_))
    else:
        for c in catalog.courses:
            if CREDIT_ONLY in c.tags:
                continue
            if idx.matches(selector, c.code):
                out.append(c.code)
            if len(out) >= limit * 4:
                break
    out = [c for c in out if idx.known(c) and CREDIT_ONLY not in _tags(idx, c)]
    # Prefer courses that are actually offered, then lower numbers.
    out.sort(key=lambda c: (not offered(idx, c), c))
    return out[:limit]


def requirements_brief(
    state: PlanState,
    rules: RuleSet,
    catalog: Catalog,
    report: Report,
    *,
    max_candidates: int = 40,
    labels: dict[str, str] | None = None,
) -> str:
    """One `## program` block per program, one line per unmet requirement unit."""
    idx = Index(catalog, rules)
    progress = {(p.program_id, p.node_id): p for p in report.progress}
    facts = PlanFacts(state, idx)
    lines: list[str] = []
    for program in plan_programs(state, rules):
        label = (labels or {}).get(program.id, program.id)
        lines.append(f"## {program.id}: {label}")
        compiled = compile_program(program, facts, idx)
        seq_flags: dict[str, set[str]] = {}
        for scope in compiled.scopes:
            c = scope.constraints
            for u in scope.units:
                if c.same_sequence:
                    seq_flags.setdefault(u, set()).add("all from one sequence")
                if c.in_order:
                    seq_flags.setdefault(u, set()).add("in order")
        for path, unit in compiled.units.items():
            row = progress.get((program.id, path))
            if row is not None and row.satisfied:
                continue
            need = unit.need or (unit.need_units or 0) // 100
            desc = describe_selector(unit.selector, idx)
            cands = _candidates(idx, catalog, unit.selector, max_candidates)
            cand_txt = "; ".join(candidate_text(idx, c) for c in cands)
            flags = []
            if unit.no_pass_fail:
                flags.append("letter grade")
            if unit.min_grade:
                flags.append(f"min {unit.min_grade}")
            flags.extend(sorted(seq_flags.get(path, ())))
            lines.append(
                f"- {path} ({unit.label or 'required'}): need {need}"
                + (f" (have {row.have})" if row is not None and row.have else "")
                + f". Counts: {desc[:220]}"
                + (f" [{', '.join(flags)}]" if flags else "")
                + (f"\n    candidates: {cand_txt}" if cand_txt else "")
            )
    return "\n".join(lines)


def known_codes(state: PlanState, catalog: Catalog) -> set[str]:
    """Every code the model may use: the catalog's courses and the plan's own items."""
    codes = {c.code for c in catalog.courses}
    codes |= {i.course for i in state.items or [] if i.course}
    return codes
