"""Shared plumbing for the campus agents (docs/BEST-OF-UCHICAGO-PLAN.md): the interviewer and
the Commons bot. (The Ask chatbot and the route drafter went in issue #15, the Feed's notes in
issue #19.)

- `run_live` runs an agent in a worker thread and yields a `LiveStep` each time the model calls
  a tool, so the page can show the agent working ("Reading CMSC 14100") while it thinks. Only the
  worker thread touches the database session while the run lasts; the caller waits on a queue.
- `campus_toolbox` gives the advisor's read tools (catalog, programs, forum) without a plan.
- `known_courses` / `course_codes_in` check course codes against the catalog, so no agent can
  link a course that does not exist (CLAUDE.md: never invent catalog facts).
"""

from __future__ import annotations

import queue
import re
import threading
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Any, Literal

import sqlalchemy as sa
from llm_gateway.api import AgentError, AgentResult, AgentSpec, run_agent
from llm_gateway.types import CallSink, Tool, ToolOutput
from planner_core.models import PlanState, Report
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.agents.tools import ToolBox
from api.db import models as m
from api.repo import catalog as catalog_repo

#: The catalog year the campus agents read (the only one seeded).
CAMPUS_YEAR = "2026-27"
CAMPUS_ENTRY_TERM = "2026-AU"

#: "CMSC 14100", "MATH 20700", "HUMA 11000": a subject of 2-5 letters and a 5-digit number.
COURSE_CODE = re.compile(r"\b([A-Z]{2,5})\s?(\d{5})\b")


@dataclass(frozen=True)
class LiveStep:
    """One tool call, as the page shows it: `label` is plain English ("Searching the catalog
    for 'quantum'"), built by the server from the tool name and its input."""

    tool: str
    label: str
    status: Literal["started", "done", "failed"]


Labeler = Callable[[str, dict[str, Any]], str]


def default_label(tool: str, args: dict[str, Any]) -> str:
    """A short description of a tool call. Text from the model is cut to 60 characters."""

    def arg(name: str) -> str:
        return str(args.get(name) or "").strip()[:60]

    if tool == "search_courses":
        q = arg("query") or arg("q") or arg("subject")
        return f"Searching the catalog for “{q}”" if q else "Searching the catalog"
    if tool == "get_course":
        return f"Reading {arg('code')}" if arg("code") else "Reading a course"
    if tool == "compare_courses":
        codes = args.get("codes") or []
        return "Comparing " + ", ".join(str(c)[:16] for c in codes[:4])
    if tool == "get_program":
        return f"Checking the rules of {arg('program_id')}"
    if tool == "list_programs":
        return "Looking through majors and minors"
    if tool in ("get_forum_summary", "get_forum_posts"):
        return f"Reading what students say about {arg('code')}".rstrip()
    if tool == "search_commons":
        return "Searching forum questions"
    if tool == "get_profile":
        return "Remembering what you told me"
    if tool == "campus_guide":
        return "Checking the campus guide"
    return tool.replace("_", " ").capitalize()


def _wrap(tool: Tool, out: queue.Queue[Any], label: Labeler) -> Tool:
    def handler(args: dict[str, Any]) -> ToolOutput:
        text = label(tool.name, args)
        out.put(LiveStep(tool.name, text, "started"))
        try:
            result = tool.handler(args)
        except Exception:
            out.put(LiveStep(tool.name, text, "failed"))
            raise
        out.put(LiveStep(tool.name, text, "failed" if result.is_error else "done"))
        return result

    return replace(tool, handler=handler)


_DONE = object()


def run_live[T: BaseModel](
    llm: object,
    spec: AgentSpec[T],
    *,
    sink: CallSink | None = None,
    label: Labeler = default_label,
    poll_s: float = 0.25,
) -> Iterator[LiveStep | AgentResult[T]]:
    """Run `spec` in a worker thread; yield a `LiveStep` per tool call as it happens, then the
    `AgentResult`. Raises `AgentError` (or whatever the run raised) after the steps."""
    out: queue.Queue[Any] = queue.Queue()
    live = replace(spec, tools=[_wrap(t, out, label) for t in spec.tools])
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["result"] = run_agent(llm, live, sink=sink)
        except BaseException as exc:  # handed to the caller's thread below
            box["error"] = exc
        finally:
            out.put(_DONE)

    thread = threading.Thread(target=work, name=f"agent-{spec.task}", daemon=True)
    thread.start()
    while True:
        try:
            item = out.get(timeout=poll_s)
        except queue.Empty:
            continue
        if item is _DONE:
            break
        yield item
    thread.join()
    if "error" in box:
        raise box["error"]
    yield box["result"]


def campus_toolbox(db: Session, *, logged_in: bool, show_unpublished: bool) -> ToolBox:
    """The advisor's read tools without a student plan (an empty plan, no issues)."""
    state = PlanState(catalog_year=CAMPUS_YEAR, entry_term=CAMPUS_ENTRY_TERM)
    report = Report(status="valid", plan_hash="campus", core_version="campus")
    return ToolBox(
        db=db,
        state=state,
        report=report,
        statuses=catalog_repo.ALL_STATUSES if show_unpublished else catalog_repo.PUBLISHED,
        show_unpublished=show_unpublished,
        logged_in=logged_in,
    )


def normalize_code(code: str) -> str | None:
    """'cmsc14100' / 'CMSC 14100' -> 'CMSC 14100'; None when it is not a course code."""
    match = COURSE_CODE.search(code.strip().upper())
    return f"{match.group(1)} {match.group(2)}" if match else None


def known_courses(db: Session, codes: Iterable[str]) -> dict[str, str]:
    """{code: title} for the codes that exist in the catalog (others are left out)."""
    wanted = {c for c in (normalize_code(x) for x in codes) if c}
    if not wanted:
        return {}
    rows = db.execute(
        sa.select(m.Course.code, m.Course.title).where(
            m.Course.catalog_year == CAMPUS_YEAR, m.Course.code.in_(sorted(wanted))
        )
    ).all()
    return {code: title for code, title in rows}


def course_codes_in(db: Session, text: str, limit: int = 12) -> dict[str, str]:
    """The real courses a text mentions, in order of first mention: {code: title}."""
    seen: list[str] = []
    for match in COURSE_CODE.finditer(text.upper()):
        code = f"{match.group(1)} {match.group(2)}"
        if code not in seen:
            seen.append(code)
    found = known_courses(db, seen[: limit * 2])
    return {c: found[c] for c in seen if c in found}


__all__ = [
    "CAMPUS_YEAR",
    "AgentError",
    "LiveStep",
    "campus_toolbox",
    "course_codes_in",
    "default_label",
    "known_courses",
    "normalize_code",
    "run_live",
]
