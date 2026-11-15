"""Parser self-repair (SPEC "Quarterly schedule pipeline", step 4).

When a run fails (a page does not fit the layout, or zero rows), the `scraper_repair` agent
gets the failing snapshots, the old parser (its source and its selectors) and the errors, and
proposes new *selectors* (a `ParserConfig`, never code). A proposal counts only if, on stored
snapshots:

- it reproduces the last good run's section count on every snapshot of that run, and
- it parses every snapshot of the failed run without an error, with at least one section.

Code re-checks this after the agent finishes. The result is always a `schedule_parser_repair`
review item; the parser changes only when a curator accepts it (`pipeline.active_config`).
If no valid proposal comes back, the review item says parsing is broken and needs a developer.

The agent reads untrusted page HTML, so its tools are read-only (SPEC "Untrusted content").
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any

import api.db.models as m
import sqlalchemy as sa
from api.attributes.a3 import load_prompt
from api.forum.moderation import wrap_untrusted
from llm_gateway.api import (
    AgentError,
    AgentSpec,
    Budget,
    CallSink,
    Message,
    SubmitTool,
    Tool,
    ToolOutput,
    run_agent,
)
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from scraper import parse, review
from scraper.parse import ParseError, ParserConfig, parse_page
from scraper.pipeline import RUN_KIND, active_config
from scraper.snapshots import SnapshotStore, read_snapshot

TASK = "scraper_repair"
PROMPT = "scraper_repair"
SLICE = 10_000  # characters of HTML per read_snapshot call (the loop caps results at 12k)
BUDGET = Budget(tool_calls=16, tokens=200_000, seconds=300)


class RepairProposal(BaseModel):
    config: ParserConfig
    explanation: str = Field(max_length=2000)


@dataclass
class Verification:
    ok: bool
    #: snapshot id -> (expected, got) for the last good run's snapshots
    good: dict[int, tuple[int, int | None]] = field(default_factory=dict)
    #: snapshot id -> sections parsed from the failed run's snapshots (None: error)
    failed: dict[int, int | None] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def as_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "good": {str(k): {"expected": e, "got": g} for k, (e, g) in self.good.items()},
            "failed": {str(k): v for k, v in self.failed.items()},
            "problems": self.problems,
        }


def _count(html: str, config: ParserConfig) -> tuple[int | None, str | None]:
    try:
        return len(parse_page(html, config)), None
    except ParseError as exc:
        return None, str(exc)


def verify_config(
    pages: dict[int, str],
    config: ParserConfig,
    *,
    good_counts: dict[int, int],
    failed_ids: list[int],
) -> Verification:
    """Check a proposal against stored snapshots (`pages`: snapshot id -> HTML)."""
    result = Verification(ok=True)
    for sid, expected in sorted(good_counts.items()):
        got, error = _count(pages[sid], config)
        result.good[sid] = (expected, got)
        if got != expected:
            result.problems.append(
                f"snapshot {sid} (last good run): expected {expected} sections, got "
                f"{got if got is not None else 'an error: ' + str(error)}"
            )
    total = 0
    for sid in failed_ids:
        got, error = _count(pages[sid], config)
        result.failed[sid] = got
        if got is None:
            result.problems.append(f"snapshot {sid} (failed run) still fails: {error}")
        else:
            total += got
    if failed_ids and total == 0:
        result.problems.append("the failed run's snapshots still parse to zero sections")
    result.ok = not result.problems
    return result


def last_good_run(db: Session, before_id: int) -> m.ExtractionRun | None:
    return db.scalar(
        sa.select(m.ExtractionRun)
        .where(
            m.ExtractionRun.kind == RUN_KIND,
            m.ExtractionRun.status == "ok",
            m.ExtractionRun.id < before_id,
        )
        .order_by(m.ExtractionRun.id.desc())
        .limit(1)
    )


def _tools(pages: dict[int, str], good: dict[int, int], failed: list[int]) -> list[Tool]:
    def read(args: dict[str, Any]) -> ToolOutput:
        sid, offset = int(args["snapshot_id"]), max(0, int(args["offset"]))
        if sid not in pages:
            return ToolOutput(f"unknown snapshot {sid}; use one of {sorted(pages)}", is_error=True)
        html = pages[sid]
        chunk = html[offset : offset + SLICE]
        header = f"snapshot {sid}, characters {offset}-{offset + len(chunk)} of {len(html)}"
        return ToolOutput(f"{header}\n{wrap_untrusted(chunk, f'snapshot-{sid}')}")

    def try_config(args: dict[str, Any]) -> ToolOutput:
        try:
            config = ParserConfig.model_validate(args.get("config"))
        except ValidationError as exc:
            return ToolOutput(f"invalid config: {exc}", is_error=True)
        result = verify_config(pages, config, good_counts=good, failed_ids=failed)
        return ToolOutput(json.dumps(result.as_json()))

    return [
        Tool(
            name="read_snapshot",
            description=(
                "Read part of a stored page's HTML (untrusted data). Returns at most "
                f"{SLICE} characters from `offset`."
            ),
            input_schema={
                "type": "object",
                "properties": {"snapshot_id": {"type": "integer"}, "offset": {"type": "integer"}},
                "required": ["snapshot_id", "offset"],
                "additionalProperties": False,
            },
            handler=read,
        ),
        Tool(
            name="try_config",
            description=(
                "Run the parser with proposed selectors on the stored snapshots and report the "
                "section counts against the last good run, and any errors. Read-only."
            ),
            input_schema={
                "type": "object",
                "properties": {"config": ParserConfig.model_json_schema()},
                "required": ["config"],
            },
            handler=try_config,
            strict=False,
        ),
    ]


def propose_repair(
    db: Session,
    store: SnapshotStore,
    llm: object,
    failed_run_id: int,
    *,
    sink: CallSink | None = None,
) -> m.ReviewItem:
    """Ask the agent for new selectors after a failed run; always returns the review item
    (with a verified proposal, or saying none was found). The caller commits."""
    failed = db.get(m.ExtractionRun, failed_run_id)
    if failed is None or failed.kind != RUN_KIND or failed.status != "failed":
        raise ValueError(f"run {failed_run_id} is not a failed schedule run")
    good_run = last_good_run(db, failed_run_id)
    good_counts = (
        {int(k): int(v) for k, v in (good_run.output or {}).get("counts_by_snapshot", {}).items()}
        if good_run is not None
        else {}
    )
    failed_ids = list(failed.input_snapshot_ids)
    pages = {sid: read_snapshot(db, store, sid)[1] for sid in {*good_counts, *failed_ids}}
    old = active_config(db)
    errors = (failed.output or {}).get("errors", [])

    def check(proposal: RepairProposal) -> None:
        result = verify_config(
            pages, proposal.config, good_counts=good_counts, failed_ids=failed_ids
        )
        if not result.ok:
            raise ValueError("; ".join(result.problems))

    prompt = load_prompt(PROMPT)
    brief = {
        "failed_run_id": failed_run_id,
        "failed_snapshot_ids": failed_ids,
        "errors": errors,
        "last_good_run_id": good_run.id if good_run else None,
        "last_good_counts_by_snapshot": {str(k): v for k, v in good_counts.items()},
        "old_config": old.model_dump(),
    }
    spec = AgentSpec(
        task=TASK,
        prompt_version=prompt.version,
        system=prompt.system,
        messages=[
            Message(
                "user",
                "The schedule parser failed. Details (trusted, from our own code):\n"
                f"{json.dumps(brief, indent=1)}\n\nThe old parser's source (trusted):\n"
                f"```python\n{inspect.getsource(parse)}\n```",
            )
        ],
        tools=_tools(pages, good_counts, failed_ids),
        submit=SubmitTool(
            name="submit_parser_config",
            description="Submit the new selectors. They must pass try_config.",
            model=RepairProposal,
            check=check,
        ),
        budget=BUDGET,
    )
    base = {
        "failed_run_id": failed_run_id,
        "last_good_run_id": good_run.id if good_run else None,
        "snapshot_ids": failed_ids,
        "errors": errors,
        "old_config": old.model_dump(),
    }
    try:
        result = run_agent(llm, spec, sink=sink)
    except AgentError as exc:
        return review.open_review(
            db,
            review.PARSER_REPAIR,
            f"run:{failed_run_id}",
            {**base, "proposed_config": None, "agent_error": str(exc)[:500]},
            "The schedule pages no longer fit the parser and the repair agent found no fix "
            f"({exc.reason}). A developer needs to update the parser selectors.",
        )
    proposal = result.output
    # Never trust the agent's own check: verify again before a human sees it.
    verification = verify_config(
        pages, proposal.config, good_counts=good_counts, failed_ids=failed_ids
    )
    if not verification.ok:  # pragma: no cover - the submit check already enforced this
        return review.open_review(
            db,
            review.PARSER_REPAIR,
            f"run:{failed_run_id}",
            {**base, "proposed_config": None, "verification": verification.as_json()},
            "The repair agent's proposal failed verification. A developer needs to look.",
        )
    return review.open_review(
        db,
        review.PARSER_REPAIR,
        f"run:{failed_run_id}",
        {
            **base,
            "proposed_config": proposal.config.model_dump(),
            "explanation": proposal.explanation,
            "verification": verification.as_json(),
            "tokens": result.tokens,
        },
        "The schedule pages changed layout. The repair agent proposes new parser selectors; "
        "they reproduce the last good counts on the stored pages and parse the new ones. "
        "Accepting switches the parser to them; then re-run the failed schedule run.",
    )
