"""Agent E3: the program formalizer (SPEC step 5, "E1-E4. Ingestion agents").

Run twice, independently: run A is task `e3_program_formalizer` with `prompts/e3_formalizer.md`;
run B is task `e3b_second_opinion` (a different model, see `llm_routing.yaml`) with
`prompts/e3b_formalizer.md`, the same instructions in a different order, and the facts in the
first message reordered too.

Tools (fixed list):
- `read_snapshot(id, start, end)`: page text, inside `<untrusted_source>`;
- `lookup_course(code)`, `get_course_list(name)`: catalog facts;
- `validate_rules(rules_yaml)`: the deterministic checks (a), (b), (c), (g); 5 attempts;
- `run_golden(program)`: the golden plans against the last tree `validate_rules` accepted;
- `submit_rules(rules_yaml, notes)`: ends the run. The submission must pass (a)-(c), with one
  repair turn; otherwise the run fails and the program goes to review without a tree.
Output always lands in the review queue (never `published`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml
from api.agents.prompts import load_prompt
from api.agents.tools import untrusted
from llm_gateway.api import (
    AgentSpec,
    Budget,
    LLMUnavailableError,
    Message,
    SubmitTool,
    Tool,
    ToolOutput,
    run_agent,
)
from llm_gateway.loop import to_json
from planner_core.models import ProgramRules
from pydantic import BaseModel, Field

from worker.ingest import courseleaf
from worker.ingest.catalog import CatalogView
from worker.ingest.e2 import ProgramCandidate
from worker.ingest.golden import GoldenOutcome, GoldenRunner
from worker.ingest.llm import model_of
from worker.ingest.records import RunRecord
from worker.ingest.snapshots import Snapshot
from worker.ingest.validators import Check, deterministic_problems

READ_LIMIT = 10_000
VALIDATE_ATTEMPTS = 5


@dataclass(frozen=True)
class RunVariant:
    kind: str  # e3 | e3b
    task: str
    prompt: str
    facts_first: bool  # run B puts the page list before the program facts


RUN_A = RunVariant("e3", "e3_program_formalizer", "e3_formalizer", facts_first=False)
RUN_B = RunVariant("e3b", "e3b_second_opinion", "e3b_formalizer", facts_first=True)


class E3Submission(BaseModel):
    rules_yaml: str = Field(min_length=1)
    notes: str = ""


@dataclass
class E3Run:
    variant: RunVariant
    rules: ProgramRules | None
    error: str | None = None
    validate_attempts: int = 0
    golden: GoldenOutcome | None = None
    warnings: list[Check] = field(default_factory=list)
    run: RunRecord | None = None
    notes: str = ""


@dataclass
class E3Context:
    candidate: ProgramCandidate
    catalog_year: str
    snapshots: list[Snapshot]
    catalog: CatalogView
    golden: GoldenRunner | None = None

    def __post_init__(self) -> None:
        self.texts = {s.id: courseleaf.page_text(s.text()) for s in self.snapshots}
        self.ids_by_url = {s.url: s.id for s in self.snapshots}


def parse_rules_yaml(text: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"the YAML does not parse: {exc}") from exc


def _problems(checks: list[Check], blocking: set[str]) -> list[str]:
    return [f"({c.id}) {p}" for c in checks if c.id in blocking and not c.ok for p in c.problems]


def _validate(ctx: E3Context, text: str) -> tuple[ProgramRules | None, list[Check]]:
    raw = parse_rules_yaml(text)
    if isinstance(raw, dict):
        if raw.get("id") not in (None, ctx.candidate.id):
            raise ValueError(f"the tree's id must be {ctx.candidate.id}")
        if str(raw.get("catalog_year", ctx.catalog_year)) != ctx.catalog_year:
            raise ValueError(f"the tree's catalog_year must be {ctx.catalog_year}")
        raw = {"id": ctx.candidate.id, "catalog_year": ctx.catalog_year, **raw}
        raw.setdefault("type", ctx.candidate.type)
    return deterministic_problems(raw, ctx.catalog, ctx.texts, ctx.ids_by_url, ctx.candidate.type)


def _tools(ctx: E3Context, state: dict[str, Any]) -> list[Tool]:
    def read_snapshot(args: dict[str, Any]) -> ToolOutput:
        sid = str(args.get("id", ""))
        if sid not in ctx.texts:
            return ToolOutput(f"No snapshot {sid!r}. Known: {sorted(ctx.texts)}", is_error=True)
        text = ctx.texts[sid]
        start = max(0, int(args.get("start", 0)))
        end = min(
            len(text), max(start, int(args.get("end", start + READ_LIMIT))), start + READ_LIMIT
        )
        return ToolOutput(
            f"Characters {start}-{end} of {len(text)}:\n"
            + untrusted(f"snapshot:{sid}", text[start:end]),
            ids=frozenset({f"snapshot:{sid}"}),
        )

    def lookup_course(args: dict[str, Any]) -> ToolOutput:
        code = " ".join(str(args.get("code", "")).upper().split())
        facts = ctx.catalog.courses.get(code)
        if facts is None:
            return ToolOutput(f"{code} is not in the {ctx.catalog_year} catalog.", is_error=True)
        return ToolOutput(
            to_json(
                {
                    "code": facts.code,
                    "title": facts.title,
                    "units": facts.units,
                    "crosslists": list(facts.crosslists),
                }
            ),
            ids=frozenset({f"course:{code}"}),
        )

    def get_course_list(args: dict[str, Any]) -> ToolOutput:
        name = str(args.get("name", ""))
        cl = ctx.catalog.lists.get(name)
        if cl is None:
            return ToolOutput(
                f"No course list {name!r}. Known lists: {', '.join(sorted(ctx.catalog.lists))}",
                is_error=True,
            )
        return ToolOutput(
            to_json(
                {"name": cl.name, "label": cl.label, "courses": cl.courses, "sublists": cl.sublists}
            ),
            ids=frozenset({f"list:{name}"}),
        )

    def validate_rules(args: dict[str, Any]) -> ToolOutput:
        if state["attempts"] >= VALIDATE_ATTEMPTS:
            return ToolOutput(
                f"No validation attempts left ({VALIDATE_ATTEMPTS} used). Submit your best tree.",
                is_error=True,
            )
        state["attempts"] += 1
        left = VALIDATE_ATTEMPTS - state["attempts"]
        try:
            rules, checks = _validate(ctx, str(args.get("rules_yaml", "")))
        except ValueError as exc:
            return ToolOutput(to_json({"ok": False, "attempts_left": left, "errors": [str(exc)]}))
        errors = _problems(checks, {"a", "b", "c"})
        warnings = _problems(checks, {"g"})
        if rules is not None and not errors:
            state["valid"] = rules
        return ToolOutput(
            to_json(
                {"ok": not errors, "attempts_left": left, "errors": errors, "warnings": warnings}
            )
        )

    def run_golden(args: dict[str, Any]) -> ToolOutput:
        if str(args.get("program", "")) != ctx.candidate.id:
            return ToolOutput(f"This run formalizes {ctx.candidate.id} only.", is_error=True)
        rules = state.get("valid")
        if rules is None:
            return ToolOutput(
                "Call validate_rules first; no tree has passed it yet.", is_error=True
            )
        if ctx.golden is None:
            return ToolOutput("There are no golden plans for this catalog year.")
        outcome = ctx.golden(rules)
        state["golden"] = outcome
        return ToolOutput(outcome.summary())

    code = {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
        "additionalProperties": False,
    }
    return [
        Tool(
            "read_snapshot",
            f"Read characters start..end (at most {READ_LIMIT}) of a fetched page's text.",
            {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
                "required": ["id", "start", "end"],
                "additionalProperties": False,
            },
            read_snapshot,
        ),
        Tool("lookup_course", "Look up one course by code, e.g. CMSC 14100.", code, lookup_course),
        Tool(
            "get_course_list",
            "Read a named course list (for `from: {list: ...}` selectors).",
            {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            get_course_list,
        ),
        Tool(
            "validate_rules",
            "Check a rule tree (YAML). Returns errors to fix. "
            f"At most {VALIDATE_ATTEMPTS} calls per run.",
            {
                "type": "object",
                "properties": {"rules_yaml": {"type": "string"}},
                "required": ["rules_yaml"],
                "additionalProperties": False,
            },
            validate_rules,
        ),
        Tool(
            "run_golden",
            "Run the golden plans for this program against the last tree validate_rules accepted.",
            {
                "type": "object",
                "properties": {"program": {"type": "string"}},
                "required": ["program"],
                "additionalProperties": False,
            },
            run_golden,
        ),
    ]


def first_message(ctx: E3Context, variant: RunVariant) -> str:
    c = ctx.candidate
    program = (
        f"Program: {c.name} (id `{c.id}`, type {c.type}"
        + (f", degree {c.degree}" if c.degree else "")
        + f"), catalog year {ctx.catalog_year}."
    )
    pages = "Fetched pages (snapshot ids):\n" + "\n".join(
        f"- `{s.id}`: {s.url} ({len(ctx.texts[s.id])} characters)" for s in ctx.snapshots
    )
    lists = "Named course lists: " + (", ".join(sorted(ctx.catalog.lists)) or "none")
    parts = [pages, lists, program] if variant.facts_first else [program, pages, lists]
    return "\n\n".join(parts) + "\n\nFormalize this program's requirements, then call submit_rules."


def formalize_program(
    llm: Any, ctx: E3Context, variant: RunVariant = RUN_A, budget: Budget | None = None
) -> E3Run:
    prompt = load_prompt(variant.prompt)
    state: dict[str, Any] = {"attempts": 0, "valid": None, "golden": None}
    accepted: dict[str, Any] = {}
    spent = float(getattr(llm, "spent", 0.0))

    def check(sub: E3Submission) -> None:
        rules, checks = _validate(ctx, sub.rules_yaml)
        errors = _problems(checks, {"a", "b", "c"})
        if rules is None or errors:
            raise ValueError("; ".join(errors[:12]) or "the tree is not valid")
        accepted["rules"] = rules
        accepted["warnings"] = [c for c in checks if c.id == "g" and not c.ok]

    spec = AgentSpec(
        task=variant.task,
        prompt_version=prompt.version_tag,
        system=prompt.text,
        messages=[Message("user", first_message(ctx, variant))],
        submit=SubmitTool(
            name="submit_rules",
            description="Submit the finished rule tree (YAML) and any notes for the reviewer.",
            model=E3Submission,
            check=check,
        ),
        tools=_tools(ctx, state),
        budget=budget or Budget(tool_calls=40, tokens=500_000, seconds=900),
    )
    try:
        result = run_agent(llm, spec)
    except LLMUnavailableError as exc:
        out = E3Run(variant, None, error=str(exc), validate_attempts=state["attempts"])
        output = None
    else:
        rules = accepted["rules"]
        golden = ctx.golden(rules) if ctx.golden is not None else None
        out = E3Run(
            variant,
            rules,
            validate_attempts=state["attempts"],
            golden=golden,
            warnings=accepted.get("warnings", []),
            notes=result.output.notes,
        )
        output = {"rules": rules.model_dump(mode="json"), "notes": result.output.notes}
    out.run = RunRecord(
        kind=variant.kind,
        model=model_of(llm, variant.task),
        prompt_version=prompt.version_tag,
        input_snapshot_ids=[s.id for s in ctx.snapshots],
        output=output,
        status="ok" if out.rules is not None else "failed",
        cost_usd=float(getattr(llm, "spent", 0.0)) - spent,
    )
    return out
