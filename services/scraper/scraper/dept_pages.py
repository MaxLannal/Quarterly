"""Department offering pages (SPEC "Sources": planned offerings for the coming year), starting
with the CS course-info pages. An E-style extraction: the model returns planned offerings,
each with a verbatim quote, and code checks every item before a human sees it:

- the quote appears in the page text (whitespace-insensitive);
- the course code appears in the quote, and is in the catalog (otherwise it is listed as
  unknown, not applied);
- every quarter claimed is named in the quote ("Autumn", "Aut", ...);
- an instructor name, if given, appears in the quote.

The result is one `schedule_dept_plan` review item. Nothing is applied until a curator accepts
it (`scraper.apply.apply_department_plan_item`, which sets p = 0.95).

The page is untrusted: it reaches the model inside `<untrusted_source>` tags and the call has
no tools.
"""

from __future__ import annotations

import html
from typing import Literal

import api.db.models as m
import sqlalchemy as sa
from api.attributes.a3 import load_prompt
from api.forum.moderation import wrap_untrusted
from llm_gateway.api import LLM, Message
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from scraper import review
from scraper.dom import parse_html
from scraper.parse import CODE_RE
from scraper.snapshots import SnapshotStore, read_snapshot

TASK = "dept_offerings_extraction"
PROMPT = "dept_offerings"
RUN_KIND = "dept_offerings"
Quarter = Literal["AU", "WI", "SP", "SU"]
QUARTER_WORDS: dict[str, tuple[str, ...]] = {
    "AU": ("autumn", "aut", "fall"),
    "WI": ("winter", "win"),
    "SP": ("spring", "spr"),
    "SU": ("summer", "sum"),
}


class PlannedOffering(BaseModel):
    course_code: str = Field(max_length=16)
    quarters: list[Quarter] = Field(min_length=1, max_length=4)
    instructor: str | None = Field(default=None, max_length=120)
    quote: str = Field(max_length=500)


class DeptPlan(BaseModel):
    offerings: list[PlannedOffering] = Field(default_factory=list, max_length=400)


def _norm(text: str) -> str:
    return " ".join(html.unescape(text).lower().split())


def page_text(raw_html: str) -> str:
    return parse_html(raw_html).lines()


def check_offering(item: PlannedOffering, text: str) -> str | None:
    """The reason the item is rejected, or None if every claim is backed by its quote."""
    quote = _norm(item.quote)
    if not quote or quote not in _norm(text):
        return "the quote is not on the page"
    code = CODE_RE.search(item.course_code.upper())
    if code is None:
        return "not a course code"
    if not any(
        c == (code.group(1), code.group(2)) for c in CODE_RE.findall(html.unescape(item.quote))
    ):
        return "the course code is not in the quote"
    words = set(quote.replace(",", " ").replace("/", " ").split())
    for q in item.quarters:
        if not words & set(QUARTER_WORDS[q]):
            return f"the quote does not name {q}"
    if item.instructor and _norm(item.instructor) not in quote:
        return "the instructor is not in the quote"
    return None


def planned_terms(academic_year: str, quarter: str) -> str:
    """'2027-28', 'AU' -> '2027-AU'; WI and SP fall in the second calendar year; the summer
    opens the academic year (planner_core.terms)."""
    first = int(academic_year.split("-")[0])
    return f"{first + 1 if quarter in ('WI', 'SP') else first}-{quarter}"


def extract_department_plan(
    db: Session,
    store: SnapshotStore,
    llm: LLM,
    snapshot_id: int,
    *,
    department: str,
    academic_year: str,
) -> m.ReviewItem:
    """Run the extraction on one stored page and open a review item. Raises
    `LLMUnavailableError` when there is no model (the run is recorded as failed). The caller
    commits."""
    from llm_gateway.api import LLMUnavailableError

    snap, raw = read_snapshot(db, store, snapshot_id)
    text = page_text(raw)
    prompt = load_prompt(PROMPT)
    run = m.ExtractionRun(
        kind=RUN_KIND,
        model=TASK,  # routing task; model ids live in llm_routing.yaml
        prompt_version=prompt.version,
        input_snapshot_ids=[snapshot_id],
        status="running",
    )
    db.add(run)
    db.flush()
    try:
        raw_plan = llm.structured(
            TASK,
            system=prompt.system,
            messages=[
                Message(
                    "user",
                    f"Department: {department}. Academic year: {academic_year}.\n\n"
                    + wrap_untrusted(text, f"snapshot-{snapshot_id}"),
                )
            ],
            schema=DeptPlan,
            prompt_version=prompt.version,
            timeout_s=120,
        )
    except LLMUnavailableError as exc:
        run.status = "failed"
        run.output = {"error": str(exc)[:500]}
        db.flush()
        raise

    accepted: list[dict[str, object]] = []
    unknown: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for item in raw_plan.offerings:
        reason = check_offering(item, text)
        row = item.model_dump()
        if reason is not None:
            rejected.append({**row, "rejected_because": reason})
            continue
        code_m = CODE_RE.search(item.course_code.upper())
        assert code_m is not None
        code = f"{code_m.group(1)} {code_m.group(2)}"
        row["course_code"] = code
        row["terms"] = [planned_terms(academic_year, q) for q in item.quarters]
        exists = db.scalar(sa.select(m.Course.id).where(m.Course.code == code).limit(1))
        (accepted if exists is not None else unknown).append(row)

    output = {"accepted": accepted, "unknown_codes": unknown, "rejected": rejected}
    run.status = "ok"
    run.output = output
    db.flush()
    return review.open_review(
        db,
        review.DEPT_PLAN,
        f"{department}:{academic_year}",
        {
            "department": department,
            "academic_year": academic_year,
            "snapshot_id": snapshot_id,
            "url": snap.url,
            "run_id": run.id,
            **output,
        },
        f"{department} planned offerings for {academic_year}: {len(accepted)} checked against "
        f"their quotes, {len(unknown)} with codes not in the catalog, {len(rejected)} rejected. "
        "Accepting sets the chance of offering to 95% for the accepted ones.",
    )
