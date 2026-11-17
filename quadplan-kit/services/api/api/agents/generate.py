"""A1 plan generator harness (SPEC "A1. Plan generator").

The LLM chooses *what is worth taking*; the solver decides *where it fits*; the verifier
decides *whether it is valid*. Only steps 3 and 6 call a model, and each has a fallback:

1. Load (code): plan, rules, whole catalog (done by the router before streaming).
2. Compile goals (code): inside `planner_core.generator`.
3. Choose electives (LLM): for each unmet requirement with a real choice, rank up to 8
   candidates (`search_courses`, `get_course`, `get_forum_summary`, `submit_preferences`;
   12 tool calls). Fallback: the default preferences (interest match, recommend rate).
4. Solve and 5. Verify (code): `planner_core.generator.generate`, which drops any variant
   `verify` or `check_certificate` rejects (an alert).
6. Explain (LLM): at most 25 words per quarter; the course set the model echoes must match
   the variant's, else that variant's rationale is discarded; citations not returned by a tool
   in the run are dropped. Fallback: no rationale.
7. Return each variant as a proposed change set (stored only for a saved, unchanged plan).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

from llm_gateway.api import AgentError, AgentSpec, Budget, Message, SubmitTool, run_agent
from planner_core.generator import CREDIT_ONLY, generate, open_terms
from planner_core.goalcompile import term_label
from planner_core.hashing import plan_hash
from planner_core.index import Index, PlanFacts
from planner_core.models import (
    Catalog,
    ChangeSet,
    GenerateOptions,
    PlanState,
    Report,
    RuleSet,
    Variant,
)
from planner_core.preferences import default_preference
from planner_core.programs import plan_programs
from planner_core.terms import term_key
from planner_core.tree import compile_program
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.agents.prompts import load_prompt
from api.agents.runtime import RunLog, checked_citations, split_ref, word_count
from api.agents.tools import A1_RATIONALE_TOOLS, A1_TOOLS, ToolBox
from api.db import models as m
from api.repo import plans as plans_repo
from api.schemas.agents import (
    DoneEvent,
    GenerateRequest,
    InfeasibleEvent,
    StepEvent,
    VariantEvent,
)

logger = logging.getLogger("api.agents")

TASK = "a1_plan_generator"
#: Output limits per step. Prompt 13 suggested preferences 1500 and rationale 1200; live, both
#: were cut off mid-answer (Opus 5.5 cannot turn thinking off; the rationale covers every
#: quarter of every variant), so A1 lost its rationale and Opus its preferences.
PREFERENCES_MAX_TOKENS = 4000
RATIONALE_MAX_TOKENS = 3000
PREFERENCES_BUDGET = Budget(tool_calls=12, tokens=120_000, seconds=60)
RATIONALE_BUDGET = Budget(tool_calls=6, tokens=60_000, seconds=45)
MAX_RATIONALE_WORDS = 25
MAX_PICKS = 8
#: Requirements offered to the model, and candidates shown per requirement.
MAX_NODES = 12
SHOWN_CANDIDATES = 40
SOLVER_SECONDS = 4.0

STEP_LOAD = "Loading requirements"
STEP_ELECTIVES = "Choosing electives"
STEP_DEFAULT = "Using the default elective ranking"
STEP_SOLVE = "Solving"
STEP_VERIFY = "Verifying"
STEP_RATIONALE = "Writing rationale"


# --------------------------------------------------------------------- step 3: electives


@dataclass
class ChoiceNode:
    id: str
    label: str | None
    need: int
    candidates: list[str]  # every eligible course, best default preference first
    titles: dict[str, str] = field(default_factory=dict)


def choice_nodes(
    state: PlanState, rules: RuleSet, catalog: Catalog, report: Report, interests: list[str]
) -> list[ChoiceNode]:
    """Unmet requirements where the student has a real choice (two or more candidates)."""
    idx = Index(catalog, rules)
    facts = PlanFacts(state, idx)
    unmet = {p.node_id: p for p in report.progress if not p.satisfied}
    planned = {i.course for i in state.items if i.course}
    out: list[ChoiceNode] = []
    for program in plan_programs(state, rules):
        compiled = compile_program(program, facts, idx)
        for path, unit in compiled.units.items():
            row = unmet.get(path) or (
                unmet.get(path.rsplit("/", 1)[0]) if unit.kind == "part" else None
            )
            if row is None:
                continue
            codes = [
                c.code
                for c in catalog.courses
                if c.code not in planned
                and CREDIT_ONLY not in c.tags  # received, never enrolled in (TRNC 10100)
                and idx.matches(unit.selector, c.code)
            ]
            if len(codes) < 2:
                continue
            codes.sort(key=lambda c: (-default_preference(idx, c, interests), c))
            need = max(1, row.need - row.have) if row.unit == "courses" else max(1, unit.need)
            titles = {c: getattr(idx.course(c), "title", "") for c in codes}
            out.append(ChoiceNode(path, unit.label or row.label, need, codes, titles))
            if len(out) >= MAX_NODES:
                return out
    return out


class Pick(BaseModel):
    code: str
    score: int = Field(ge=0, le=100)
    reason: str = Field(max_length=200)


class NodePicks(BaseModel):
    node_id: str
    picks: list[Pick] = Field(max_length=MAX_PICKS)


class Preferences(BaseModel):
    nodes: list[NodePicks] = Field(max_length=MAX_NODES)


_PREFERENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "picks": {
                        "type": "array",
                        "description": "Up to 8 candidates, best first.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "string"},
                                "score": {"type": "integer", "description": "0..100"},
                                "reason": {"type": "string", "description": "One short line."},
                            },
                            "required": ["code", "score", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["node_id", "picks"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["nodes"],
    "additionalProperties": False,
}


def _goal_lines(goals: list[object], interests: list[str]) -> list[str]:
    lines = [f"Interests: {', '.join(interests) if interests else 'none given'}."]
    for g in goals:
        dump = g.model_dump(mode="json", exclude_none=True) if isinstance(g, BaseModel) else g
        lines.append(f"Goal: {dump}")
    return lines


def preferences_spec(
    nodes: list[ChoiceNode], req: GenerateRequest, box: ToolBox
) -> AgentSpec[Preferences]:
    prompt = load_prompt("a1_preferences")
    by_id = {n.id: n for n in nodes}

    def check(p: Preferences) -> None:
        problems = []
        for entry in p.nodes:
            node = by_id.get(entry.node_id)
            if node is None:
                problems.append(f"unknown requirement {entry.node_id}")
                continue
            allowed = set(node.candidates)
            bad = [pick.code for pick in entry.picks if pick.code not in allowed]
            if bad:
                problems.append(f"{', '.join(bad)} cannot fill {entry.node_id}")
        if problems:
            raise ValueError("; ".join(problems))

    lines = [
        f"Catalog year {req.plan.catalog_year}; entry quarter {req.plan.entry_term}.",
        f"Programs: {', '.join(p.program_id for p in req.plan.programs) or 'none'}.",
        *_goal_lines(list(req.goals), req.interests),
        "",
        "Requirements with a choice:",
    ]
    for n in nodes:
        shown = "; ".join(
            f"{c} {n.titles.get(c, '')}".strip() for c in n.candidates[:SHOWN_CANDIDATES]
        )
        more = len(n.candidates) - SHOWN_CANDIDATES
        lines.append(
            f"- {n.id} ({n.label or 'requirement'}): needs {n.need} more; "
            f"{len(n.candidates)} candidates: {shown}"
            + (f"; and {more} more (use search_courses)" if more > 0 else "")
        )
    return AgentSpec(
        task=TASK,
        prompt_version=prompt.version_tag,
        system=prompt.text,
        messages=[Message("user", "\n".join(lines))],
        tools=box.tools(A1_TOOLS),
        submit=SubmitTool(
            "submit_preferences",
            "Submit your ranked electives for each requirement.",
            Preferences,
            input_schema=_PREFERENCES_SCHEMA,
            check=check,
            strict=True,
        ),
        budget=PREFERENCES_BUDGET,
        max_tokens=PREFERENCES_MAX_TOKENS,
    )


def to_preferences(p: Preferences) -> dict[str, int]:
    out: dict[str, int] = {}
    for entry in p.nodes:
        for pick in entry.picks:
            out[pick.code] = max(out.get(pick.code, 0), pick.score)
    return out


# --------------------------------------------------------------------- step 6: rationale


class QuarterNote(BaseModel):
    term: str
    courses: list[str]
    text: str = Field(max_length=400)
    citations: list[str] = Field(default=[], max_length=8)


class VariantNotes(BaseModel):
    label: str
    quarters: list[QuarterNote]


class Rationale(BaseModel):
    variants: list[VariantNotes]


_RATIONALE_SCHEMA = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "quarters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "term": {"type": "string", "description": "e.g. 2027-AU"},
                                "courses": {"type": "array", "items": {"type": "string"}},
                                "text": {"type": "string", "description": "At most 25 words."},
                                "citations": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["term", "courses", "text", "citations"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["label", "quarters"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["variants"],
    "additionalProperties": False,
}


def quarters_to_explain(variant: Variant, open_set: set[str]) -> dict[str, list[str]]:
    """term -> the planned courses of that quarter, for the quarters the generator planned."""
    out: dict[str, list[str]] = {}
    for item in variant.plan.items:
        if item.course and item.status == "planned" and item.term in open_set:
            out.setdefault(item.term, []).append(item.course)
    return {t: sorted(out[t]) for t in sorted(out, key=term_key)}


def rationale_spec(
    variants: list[Variant],
    quarters: dict[str, dict[str, list[str]]],
    idx: Index,
    req: GenerateRequest,
    box: ToolBox,
) -> AgentSpec[Rationale]:
    prompt = load_prompt("a1_rationale")
    known: set[str] = set()
    lines = [*_goal_lines(list(req.goals), req.interests), ""]
    for v in variants:
        avg, hardest = v.metrics.get("avg_hours"), v.metrics.get("hardest_quarter_hours")
        head = f"{v.label}"
        if avg is not None and hardest is not None:
            head += f" (average {avg:.1f} h/wk; hardest quarter {hardest:.1f} h/wk)"
        lines.append(head + ":")
        for term, codes in quarters[v.label].items():
            parts = []
            for code in codes:
                known.add(f"course:{code}")
                course = idx.course(code)
                facts = []
                for key, unit in (("workload_hours", " h/wk"), ("difficulty", "/5 difficulty")):
                    value = idx.attribute(code, key)
                    if value is not None:
                        facts.append(f"{value.value:g}{unit}")
                        known.add(f"attribute:{code}:{key}")
                title = f' "{course.title}"' if course else ""
                parts.append(f"{code}{title}" + (f" ({', '.join(facts)})" if facts else ""))
            lines.append(f"- {term} ({term_label(term)}): {'; '.join(parts)}")
    expected = {v.label: quarters[v.label] for v in variants}

    def check(r: Rationale) -> None:
        problems = []
        for vn in r.variants:
            terms = expected.get(vn.label)
            if terms is None:
                problems.append(f"unknown variant {vn.label}")
                continue
            for q in vn.quarters:
                if q.term not in terms:
                    problems.append(f"{vn.label} has no planned quarter {q.term}")
                if word_count(q.text) > MAX_RATIONALE_WORDS:
                    problems.append(f"{vn.label} {q.term}: more than 25 words")
        if problems:
            raise ValueError("; ".join(problems))

    return AgentSpec(
        task=TASK,
        prompt_version=prompt.version_tag,
        system=prompt.text,
        messages=[Message("user", "\n".join(lines))],
        tools=box.tools(A1_RATIONALE_TOOLS),
        submit=SubmitTool(
            "submit_rationale",
            "Submit one rationale per variant and quarter.",
            Rationale,
            input_schema=_RATIONALE_SCHEMA,
            check=check,
            strict=True,
        ),
        budget=RATIONALE_BUDGET,
        known_ids=known,
        max_tokens=RATIONALE_MAX_TOKENS,
    )


def apply_rationale(
    r: Rationale, quarters: dict[str, dict[str, list[str]]], seen: set[str]
) -> dict[str, tuple[dict[str, str], list[tuple[str, str, str]]]]:
    """label -> (term -> text, cited refs). A variant whose echoed course set differs from
    the plan in any quarter loses its whole rationale (the plan is kept)."""
    out: dict[str, tuple[dict[str, str], list[tuple[str, str, str]]]] = {}
    for vn in r.variants:
        expected = quarters.get(vn.label, {})
        if any(sorted(q.courses) != expected.get(q.term) for q in vn.quarters):
            logger.warning("%s: rationale for %s changed the course set; discarded", TASK, vn.label)
            continue
        texts = {q.term: q.text.strip() for q in vn.quarters}
        refs = []
        for q in vn.quarters:
            for ref in q.citations:
                parsed = split_ref(ref)
                refs.append((*parsed, parsed[1]) if parsed else ("", ref, ref))
        out[vn.label] = (texts, refs)
    return out


# --------------------------------------------------------------------- the harness


@dataclass
class GenerateRun:
    db: Session
    llm: object
    req: GenerateRequest
    rules: RuleSet
    catalog: Catalog
    box: ToolBox
    log: RunLog
    run: m.AgentRun
    #: The saved plan the variants are stored against, when the request's plan matches it.
    saved: m.Plan | None = None

    def options(self, preferences: dict[str, int] | None) -> GenerateOptions:
        r = self.req
        return GenerateOptions(
            scope=r.scope,
            selected_terms=r.selected_terms,
            today_term=r.today_term,
            load=r.load,
            per_term_load=r.per_term_load,
            max_courses_per_term=r.max_courses_per_term,
            allow_overload=r.allow_overload,
            goals=list(r.goals),
            interests=list(r.interests),
            variants=r.variants,
            preferences=preferences,
            time_limit_s=SOLVER_SECONDS,
        )

    def step(self, name: str, status: str) -> StepEvent:
        self.log.step(name, status)
        return StepEvent.model_validate({"name": name, "status": status})

    def events(self) -> Iterator[BaseModel]:
        state = self.req.plan
        yield self.step(STEP_LOAD, "started")
        report = self.box.report
        yield self.step(STEP_LOAD, "done")

        yield self.step(STEP_ELECTIVES, "started")
        preferences: dict[str, int] | None = None
        nodes = choice_nodes(state, self.rules, self.catalog, report, list(self.req.interests))
        fell_back = False
        if nodes:
            try:
                picked = run_agent(
                    self.llm, preferences_spec(nodes, self.req, self.box), sink=self.log.sink
                )
                preferences = to_preferences(picked.output) or None
                yield self.step(STEP_ELECTIVES, "done")
            except AgentError as exc:
                logger.info("%s: electives fallback (%s)", TASK, exc.reason)
                fell_back = True
                yield self.step(STEP_ELECTIVES, "failed")
                yield self.step(STEP_DEFAULT, "done")
        else:
            yield self.step(STEP_ELECTIVES, "done")

        yield self.step(STEP_SOLVE, "started")
        options = self.options(preferences)
        result = generate(state, self.rules, self.catalog, options)
        yield self.step(STEP_SOLVE, "done")
        yield self.step(STEP_VERIFY, "started")
        for alert in result.alerts:
            logger.error("%s", alert)  # a verified-plan bug; no user data in the message
        yield self.step(STEP_VERIFY, "failed" if result.alerts else "done")
        if result.infeasible is not None:
            yield InfeasibleEvent(
                message=result.infeasible.message, conflicts=result.infeasible.conflicts
            )

        notes: dict[str, tuple[dict[str, str], list[tuple[str, str, str]]]] = {}
        seen: set[str] = set()
        if result.variants:
            yield self.step(STEP_RATIONALE, "started")
            open_set = set(open_terms(state, options))
            quarters = {v.label: quarters_to_explain(v, open_set) for v in result.variants}
            try:
                idx = Index(self.catalog, self.rules)
                spec = rationale_spec(result.variants, quarters, idx, self.req, self.box)
                written = run_agent(self.llm, spec, sink=self.log.sink)
                seen = written.seen_ids
                notes = apply_rationale(written.output, quarters, seen)
                yield self.step(STEP_RATIONALE, "done")
            except AgentError as exc:
                logger.info("%s: rationale fallback (%s)", TASK, exc.reason)
                fell_back = True
                yield self.step(STEP_RATIONALE, "failed")

        base = plan_hash(state)
        for v in result.variants:
            text, refs = notes.get(v.label, ({}, []))
            cs = ChangeSet(
                origin="generate", ops=v.ops, base_plan_hash=base, preview_report=v.report
            )
            if self.saved is not None:
                row = plans_repo.store_change_set(
                    self.db,
                    self.saved,
                    origin="generate",
                    ops=v.ops,
                    base_plan_hash=base,
                    preview=v.report,
                )
                cs = plans_repo.change_set_model(row)
            yield VariantEvent(
                label=v.label,
                change_set=cs,
                report=v.report,
                rationale=text,
                citations=checked_citations(TASK, refs, seen),
                metrics=v.metrics,
            )
        self.run.status = "fallback" if fell_back else "ok"
        self.log.save(self.db, self.run)
        self.db.commit()
        yield DoneEvent(run_id=str(self.run.id))
