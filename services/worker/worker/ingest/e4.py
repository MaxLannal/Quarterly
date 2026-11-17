"""Agent E4: back-translation judge (validator (e); task `e4_backtranslation_judge`, prompt
`prompts/e4_backtranslation.md`).

Given a rule tree and the source pages, the model writes the tree back into plain English and
lists every difference from what the source says, by node path. Code keeps only differences
that name a real node path (or none: a program-wide remark). No tools; the pages are
untrusted.

`english_of` is the deterministic English rendering shown beside each node in the console
(and used by `--fake` runs as the judge's rendering).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml
from api.agents.prompts import load_prompt
from api.agents.tools import untrusted
from llm_gateway.api import LLMUnavailableError, Message
from planner_core.dsl import iter_nodes, iter_parts, node_paths
from planner_core.models import (
    BoundedPartsNode,
    Constraints,
    GroupNode,
    Part,
    ProgramRules,
    SelectNode,
    Selector,
    SlotNode,
)
from pydantic import BaseModel, Field

from worker.ingest.llm import model_of
from worker.ingest.records import RunRecord

TASK = "e4_backtranslation_judge"
PROMPT = "e4_backtranslation"
SOURCE_CHARS = 30_000


class E4Difference(BaseModel):
    path: str = ""
    problem: str = Field(min_length=1, max_length=600)


class E4Answer(BaseModel):
    english: str = Field(min_length=1)
    differences: list[E4Difference] = Field(default_factory=list)


@dataclass
class E4Result:
    answer: E4Answer | None
    differences: list[dict[str, str]] | None
    dropped: int
    run: RunRecord


# ------------------------------------------------------------------- English rendering


def selector_text(sel: Selector) -> str:
    parts = []
    if sel.codes:
        parts.append(", ".join(sel.codes))
    if sel.subject:
        parts.append(f"{sel.subject} courses")
    if sel.number_range:
        parts.append(f"numbered {sel.number_range[0]}-{sel.number_range[1]}")
    if sel.tags:
        parts.append("tagged " + ", ".join(sel.tags))
    if sel.list_:
        parts.append(f"the list {sel.list_}")
    if sel.union:
        parts.append("any of (" + "; ".join(selector_text(s) for s in sel.union) + ")")
    text = " ".join(parts)
    if sel.exclude:
        text += " except " + ", ".join(sel.exclude)
    return text


def constraints_text(c: Constraints) -> str:
    bits = []
    if c.min_grade:
        bits.append(f"grade {c.min_grade} or higher")
    if c.no_pass_fail:
        bits.append("no pass/fail")
    if c.same_sequence:
        bits.append("all from one sequence")
    if c.in_order:
        bits.append("in order")
    for cap in c.max_from:
        bits.append(f"at most {cap.n} from {selector_text(cap.selector)}")
    if c.distinct_subjects:
        bits.append(f"from at least {c.distinct_subjects} subjects")
    if c.allow_double_count:
        bits.append("may also count elsewhere")
    return "; ".join(bits)


def node_text(unit: Any) -> str:
    if isinstance(unit, SlotNode):
        text = "One of: " + ", ".join(unit.any_of) if len(unit.any_of) > 1 else unit.any_of[0]
    elif isinstance(unit, SelectNode):
        amount = (
            f"{unit.count} course{'s' if unit.count != 1 else ''}"
            if unit.count
            else f"{unit.units} units"
        )
        text = f"{amount} from {selector_text(unit.from_)}"
    elif isinstance(unit, GroupNode):
        text = "All of the following" if unit.all else f"{unit.n_of} of the following"
    elif isinstance(unit, BoundedPartsNode):
        total = (
            f"{unit.total.courses} courses" if unit.total.courses else f"{unit.total.units} units"
        )
        parts = ", ".join(f"{p.id} {p.count[0]}-{p.count[1]}" for p in unit.parts)
        text = f"{total} in parts: {parts}"
    elif isinstance(unit, Part):
        text = f"{unit.count[0]}-{unit.count[1]} from {selector_text(unit.from_)}"
    else:
        text = ""
    extra = constraints_text(unit.constraints)
    return f"{text} ({extra})" if extra else text


def english_of(rules: ProgramRules) -> str:
    lines = []
    for path, unit in [*iter_nodes(rules), *iter_parts(rules)]:
        depth = path.count("/")
        label = f"{unit.label}: " if unit.label else ""
        lines.append("  " * depth + f"- {label}{node_text(unit)}")
    return "\n".join(lines)


# ------------------------------------------------------------------------------ judge


def judge(llm: Any, rules: ProgramRules, sources: list[tuple[str, str]]) -> E4Result:
    """`sources`: (snapshot id, page text) pairs."""
    prompt = load_prompt(PROMPT)
    spent = float(getattr(llm, "spent", 0.0))
    budget = SOURCE_CHARS // max(1, len(sources))
    pages = "\n\n".join(untrusted(f"snapshot:{sid}", text[:budget]) for sid, text in sources)
    tree = yaml.safe_dump(
        rules.model_dump(mode="json", exclude_none=True), sort_keys=False, width=100
    )
    message = f"The rule tree (YAML):\n```yaml\n{tree}```\n\nThe source pages:\n{pages}"
    answer: E4Answer | None
    try:
        answer = llm.structured(
            TASK,
            system=prompt.text,
            messages=[Message("user", message)],
            schema=E4Answer,
            prompt_version=prompt.version_tag,
            timeout_s=120,
        )
    except LLMUnavailableError:
        answer = None
    differences: list[dict[str, str]] | None = None
    dropped = 0
    if answer is not None:
        known = set(node_paths(rules)) | {f"{rules.id}/policy"}
        differences = []
        for d in answer.differences:
            if d.path and d.path not in known:
                dropped += 1
                differences.append({"path": "", "problem": f"(about {d.path}) {d.problem}"})
            else:
                differences.append({"path": d.path, "problem": d.problem})
    run = RunRecord(
        kind="e4",
        model=model_of(llm, TASK),
        prompt_version=prompt.version_tag,
        input_snapshot_ids=[sid for sid, _ in sources],
        output=answer.model_dump(mode="json") if answer is not None else None,
        status="failed" if answer is None else ("ok" if not differences else "review"),
        cost_usd=float(getattr(llm, "spent", 0.0)) - spent,
    )
    return E4Result(answer, differences, dropped, run)
