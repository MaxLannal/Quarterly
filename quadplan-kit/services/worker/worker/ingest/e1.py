"""Agent E1: one prerequisite sentence -> a DSL expression (SPEC step 3; task
`e1_prereq_formalizer`, prompt `prompts/e1_prereq.md`).

The model only proposes. Code then checks, and anything that fails goes to review:
1. grammar: the answer parses as `planner_core.models.Expr`;
2. references: every course it names exists in the catalog;
3. grounding: every course number it names appears in the sentence (so "Math 15200/16200"
   may become MATH 15200 or MATH 16200, but no course appears from nowhere);
4. a course is never its own prerequisite.
The sentence is catalog text: it goes to the model inside `<untrusted_source>`, and the call
holds no tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from api.agents.prompts import load_prompt
from api.agents.tools import untrusted
from llm_gateway.api import LLM, LLMUnavailableError, Message
from planner_core.dsl import expr_courses, expr_to_text
from planner_core.models import Expr
from pydantic import BaseModel, Field, ValidationError

from worker.ingest.catalog import CatalogView
from worker.ingest.llm import model_of
from worker.ingest.records import ReviewDraft, RunRecord

TASK = "e1_prereq_formalizer"
PROMPT = "e1_prereq"


class E1Answer(BaseModel):
    """What E1 returns. `prereq` uses the DSL's short form, e.g.
    `{"all": ["CMSC 14100", {"any": ["MATH 15200", "MATH 16200"]}]}`."""

    prereq: dict[str, Any] | str | None = None
    unparseable: bool = False
    note: str = Field(default="", max_length=500)


@dataclass
class E1Result:
    course: str
    sentence: str
    expr: Expr | None
    errors: list[str] = field(default_factory=list)
    review: ReviewDraft | None = None
    run: RunRecord | None = None

    @property
    def ok(self) -> bool:
        return self.expr is not None and not self.errors


def check_expr(
    raw: dict[str, Any] | str | None, course: str, sentence: str, catalog: CatalogView
) -> tuple[Expr | None, list[str]]:
    if raw is None:
        return None, ["no expression"]
    try:
        expr = Expr.model_validate(raw)
    except ValidationError as exc:
        return None, [f"does not parse: {e['msg']}" for e in exc.errors()[:5]]
    errors = []
    named = expr_courses(expr)
    numbers = set(re.findall(r"\d{5}", sentence))
    for code in sorted(named):
        if not catalog.has_course(code):
            errors.append(f"names {code}, which is not in the catalog")
        if code.split(" ")[1] not in numbers:
            errors.append(f"names {code}, which the sentence does not mention")
    if course in named:
        errors.append(f"{course} is listed as its own prerequisite")
    return expr, errors


def formalize(
    llm: LLM,
    *,
    course: str,
    sentence: str,
    catalog: CatalogView,
    snapshot_id: str | None = None,
) -> E1Result:
    prompt = load_prompt(PROMPT)
    spent = float(getattr(llm, "spent", 0.0))
    message = f"Course: {course}\n\nThe prerequisite sentence from the catalog:\n" + untrusted(
        f"prereq:{course}", sentence
    )
    answer: E1Answer | None
    try:
        answer = llm.structured(
            TASK,
            system=prompt.text,
            messages=[Message("user", message)],
            schema=E1Answer,
            prompt_version=prompt.version_tag,
            timeout_s=30,
        )
    except LLMUnavailableError as exc:
        answer = None
        errors = [f"the model did not answer ({exc})"]
        expr = None
    if answer is not None:
        if answer.unparseable:
            expr, errors = None, ["the model could not express this sentence in the DSL"]
        else:
            expr, errors = check_expr(answer.prereq, course, sentence, catalog)
    result = E1Result(course=course, sentence=sentence, expr=expr, errors=errors)
    result.run = RunRecord(
        kind="e1",
        model=model_of(llm, TASK),
        prompt_version=prompt.version_tag,
        input_snapshot_ids=[snapshot_id] if snapshot_id else [],
        output=answer.model_dump(mode="json") if answer is not None else None,
        status="ok" if result.ok else "review",
        cost_usd=float(getattr(llm, "spent", 0.0)) - spent,
    )
    if not result.ok:
        result.review = ReviewDraft(
            target_type="requisite",
            target_id=f"{catalog.catalog_year}:{course}",
            diff={
                "kind": "requisite",
                "catalog_year": catalog.catalog_year,
                "course": course,
                "raw_text": sentence,
                "proposed": expr.model_dump(mode="json") if expr is not None else None,
                "proposed_text": expr_to_text(expr) if expr is not None else None,
                "errors": errors,
                "note": answer.note if answer is not None else "",
                "source": {"snapshot_id": snapshot_id, "quote": sentence},
            },
            reason="Prerequisite needs a person: " + "; ".join(errors),
        )
    return result


def staged_requisite(result: E1Result) -> dict[str, Any]:
    """A passing E1 result in the shape a `course_batch` item applies."""
    assert result.expr is not None
    return {
        "prereq": result.expr.model_dump(mode="json"),
        "text": expr_to_text(result.expr),
        "raw_text": result.sentence,
    }
