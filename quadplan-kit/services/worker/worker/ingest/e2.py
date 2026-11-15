"""Agent E2: the program enumerator (SPEC step 4; task `e2_program_enumerator`, prompt
`prompts/e2_enumerator.md`).

The agent reads the index pages and proposes one candidate per program (id, name, type,
degree, URL). Code then reconciles the candidates against **at least two independent
lists** built without any model (`ReferenceList`): the College's stated counts ("68 majors
and 57 minors"), the catalog's Programs of Study index, the A-Z index. Any mismatch blocks
the run (`Enumeration.blocked`): no program is formalized, and an `ingest_run` review item
explains why.

Tools: `list_pages`, `read_snapshot(id, start, end)`, and `submit_programs`. Page text is
untrusted, so the agent holds no write tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

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
from planner_core.models import Degree, ProgramType, Slug
from pydantic import BaseModel, Field

from worker.ingest import courseleaf
from worker.ingest.llm import model_of
from worker.ingest.records import ReviewDraft, RunRecord
from worker.ingest.snapshots import Snapshot

TASK = "e2_program_enumerator"
PROMPT = "e2_enumerator"
READ_LIMIT = 8000


class ProgramCandidate(BaseModel):
    id: Slug
    name: str = Field(min_length=1)
    type: ProgramType
    degree: Degree | None = None
    #: The program's name without the degree ("Computer Science" for both the BA and the
    #: BS), so a BA and a BS count as one major, as the College counts them.
    family: str = Field(min_length=1)
    url: str = Field(min_length=1)
    parent_id: Slug | None = None
    #: Snapshot ids of the pages the program was found on.
    evidence: list[str] = Field(default_factory=list)


class E2Submission(BaseModel):
    candidates: list[ProgramCandidate] = Field(min_length=1)
    note: str = ""


@dataclass
class ReferenceList:
    """A list built by code. `counts` per program type (distinct families), and/or `urls`:
    the program pages it lists, compared with candidates of the types in `url_types`."""

    name: str
    snapshot_id: str | None
    counts: dict[str, int] = field(default_factory=dict)
    urls: set[str] = field(default_factory=set)
    url_types: frozenset[str] = frozenset()
    #: False for a list that also names other pages (the A-Z index): then every proposed
    #: program must be on it, but not every page on it must be a program.
    exhaustive: bool = True


@dataclass
class Enumeration:
    candidates: list[ProgramCandidate]
    lists: list[str]
    problems: list[str]
    run: RunRecord | None = None

    @property
    def blocked(self) -> bool:
        return bool(self.problems)

    def review(self, catalog_year: str) -> ReviewDraft:
        return ReviewDraft(
            target_type="ingest_run",
            target_id=f"{catalog_year}:e2",
            diff={
                "kind": "ingest_run",
                "catalog_year": catalog_year,
                "step": "program enumeration",
                "lists": self.lists,
                "problems": self.problems,
                "candidates": [c.model_dump(mode="json") for c in self.candidates],
            },
            reason="The program count does not match the independent lists, so the run stopped "
            "before formalizing any program: " + "; ".join(self.problems[:5]),
        )


# ------------------------------------------------------------------- reference lists

COUNT = re.compile(r"\b(\d{1,3})\s+(majors|minors)\b", re.IGNORECASE)


def stated_counts(snap: Snapshot) -> ReferenceList:
    """'... offers 68 majors and 57 minors ...' -> {major: 68, minor: 57}."""
    text = courseleaf.page_text(snap.text())
    counts: dict[str, int] = {}
    for number, word in COUNT.findall(text):
        counts.setdefault(word.lower().rstrip("s"), int(number))
    return ReferenceList(name=f"stated counts ({snap.url})", snapshot_id=snap.id, counts=counts)


def url_list(
    name: str, snap: Snapshot | None, urls: list[str], types: set[str], *, exhaustive: bool = True
) -> ReferenceList:
    return ReferenceList(
        name=name,
        snapshot_id=snap.id if snap else None,
        urls=set(urls),
        url_types=frozenset(types),
        exhaustive=exhaustive,
    )


def reconcile(candidates: list[ProgramCandidate], lists: list[ReferenceList]) -> list[str]:
    problems: list[str] = []
    if len(lists) < 2:
        problems.append(f"only {len(lists)} independent list(s); at least two are required")
    ids = [c.id for c in candidates]
    problems += [
        f"program id {i} proposed twice" for i in sorted({i for i in ids if ids.count(i) > 1})
    ]
    for ref in lists:
        for ptype, expected in sorted(ref.counts.items()):
            found = len({c.family.casefold() for c in candidates if c.type == ptype})
            if found != expected:
                problems.append(f"{ref.name}: {expected} {ptype}s listed, {found} proposed")
        if ref.url_types:
            proposed = {c.url for c in candidates if c.type in ref.url_types}
            for url in sorted(ref.urls - proposed) if ref.exhaustive else []:
                problems.append(f"{ref.name}: lists {url}, but no program was proposed for it")
            for url in sorted(proposed - ref.urls):
                problems.append(
                    f"{ref.name}: does not list {url}, which a program was proposed for"
                )
    return problems


# ----------------------------------------------------------------------------- agent


def _tools(pages: dict[str, Snapshot]) -> list[Tool]:
    texts = {sid: courseleaf.page_text(s.text()) for sid, s in pages.items()}

    def list_pages(_: dict[str, Any]) -> ToolOutput:
        rows = [
            {
                "id": sid,
                "url": s.url,
                "title": courseleaf.page_title(s.text()),
                "chars": len(texts[sid]),
            }
            for sid, s in pages.items()
        ]
        return ToolOutput(to_json(rows), ids=frozenset(f"snapshot:{sid}" for sid in pages))

    def read_snapshot(args: dict[str, Any]) -> ToolOutput:
        sid = str(args.get("id", ""))
        if sid not in texts:
            return ToolOutput(f"No page with id {sid!r}; call list_pages.", is_error=True)
        start = max(0, int(args.get("start", 0)))
        end = min(
            len(texts[sid]),
            max(start, int(args.get("end", start + READ_LIMIT))),
            start + READ_LIMIT,
        )
        body = texts[sid][start:end]
        return ToolOutput(
            f"Characters {start}-{end} of {len(texts[sid])}:\n"
            + untrusted(f"snapshot:{sid}", body),
            ids=frozenset({f"snapshot:{sid}"}),
        )

    return [
        Tool(
            "list_pages",
            "List the fetched pages: id, url, title and length.",
            {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
            list_pages,
        ),
        Tool(
            "read_snapshot",
            f"Read the text of one page, characters start..end (at most {READ_LIMIT} per call).",
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
    ]


def enumerate_programs(
    llm: Any,
    *,
    catalog_year: str,
    pages: list[Snapshot],
    lists: list[ReferenceList],
    budget: Budget | None = None,
) -> Enumeration:
    prompt = load_prompt(PROMPT)
    by_id = {s.id: s for s in pages}
    spent = float(getattr(llm, "spent", 0.0))

    def check(sub: E2Submission) -> None:
        unknown = sorted({e for c in sub.candidates for e in c.evidence} - set(by_id))
        if unknown:
            raise ValueError(f"evidence names pages that do not exist: {unknown}")

    spec = AgentSpec(
        task=TASK,
        prompt_version=prompt.version_tag,
        system=prompt.text,
        messages=[
            Message(
                "user",
                f"Catalog year {catalog_year}. {len(pages)} pages were fetched. List every "
                "program of study they describe, then call submit_programs.",
            )
        ],
        submit=SubmitTool(
            name="submit_programs",
            description="Submit one candidate per program.",
            model=E2Submission,
            check=check,
        ),
        tools=_tools(by_id),
        budget=budget or Budget(tool_calls=80, tokens=600_000, seconds=900),
    )
    names = [r.name for r in lists]
    try:
        result = run_agent(llm, spec)
    except LLMUnavailableError as exc:
        out = Enumeration([], names, [f"the enumerator did not finish ({exc})"])
        status, output = "failed", None
    else:
        candidates = result.output.candidates
        out = Enumeration(candidates, names, reconcile(candidates, lists))
        status = "review" if out.blocked else "ok"
        output = result.output.model_dump(mode="json")
    out.run = RunRecord(
        kind="e2",
        model=model_of(llm, TASK),
        prompt_version=prompt.version_tag,
        input_snapshot_ids=list(by_id),
        output=output,
        status=status,
        cost_usd=float(getattr(llm, "spent", 0.0)) - spent,
    )
    return out
