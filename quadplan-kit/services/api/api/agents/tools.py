"""Read tools shared by the plan generator (A1) and the advisor chat (A2), plus the advisor's
one draft tool. Agents use the same doors as people (SPEC "Cross-cutting rules"): every tool
goes through the catalog and plan service code, never raw SQL written for the model, and none
of them writes a plan.

Every result lists the citable ids it contains (`kind:id`): `course:CODE`,
`attribute:CODE:key`, `program:ID`, `summary:PAGE_ID`, `post:POST_ID`. Forum text (posts and
the summaries made from them) is wrapped in `<untrusted_source id=...>` tags.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import sqlalchemy as sa
from llm_gateway.api import Tool, ToolOutput
from llm_gateway.loop import to_json
from planner_core import verify_checked
from planner_core.changes import ChangeOpError, apply_ops
from planner_core.dsl import iter_nodes
from planner_core.hashing import plan_hash
from planner_core.models import (
    AddOp,
    AttributeValue,
    ChangeOp,
    ChangeSet,
    MoveOp,
    PlanState,
    ProgramRules,
    RemoveOp,
    Report,
)
from planner_core.terms import term_key
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from api.attributes.records import hidden_citations
from api.db import models as m
from api.forum.pages import pages_of_code
from api.repo import catalog as catalog_repo
from api.repo.rules import UnknownProgramsError, load_verify_inputs

logger = logging.getLogger("api.agents")

MAX_RESULTS = 10
MAX_POSTS = 5
DESCRIPTION_CHARS = 700
POST_CHARS = 1500
#: Most proposals one advisor answer may make.
MAX_PROPOSALS = 2


def untrusted(source_id: str, text: str) -> str:
    """Forum text as data: escaped so it cannot close the tag or open another."""
    body = html.escape(text, quote=False)
    return f'<untrusted_source id="{source_id}">\n{body}\n</untrusted_source>'


def _attrs(code: str, values: Sequence[AttributeValue]) -> tuple[dict[str, Any], set[str]]:
    out: dict[str, Any] = {}
    ids: set[str] = set()
    for a in values:
        out[a.key] = {"value": round(a.value, 2), "n": a.n, "method": a.method}
        ids.add(f"attribute:{code}:{a.key}")
    return out, ids


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    """A strict-mode object schema: every property required, nothing else allowed."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_NULLABLE_STR = {"type": ["string", "null"]}
_CODE = {"type": "string", "description": 'A course code such as "MATH 20700".'}


class OpIn(BaseModel):
    """An edit as the model writes it: by course code and quarter (`2027-AU`)."""

    op: Literal["add", "move", "remove"]
    course: str
    term: str | None = None
    from_term: str | None = None
    to_term: str | None = None

    def to_op(self) -> ChangeOp:
        if self.op == "add":
            if self.term is None:
                raise ValueError("add needs `term`")
            return AddOp(course=self.course, term=self.term)
        if self.op == "move":
            if self.to_term is None:
                raise ValueError("move needs `to_term`")
            return MoveOp(course=self.course, from_term=self.from_term, to_term=self.to_term)
        return RemoveOp(course=self.course, term=self.term)


class OpsIn(BaseModel):
    ops: list[OpIn] = Field(min_length=1, max_length=8)


_OPS_SCHEMA = _obj(
    {
        "ops": {
            "type": "array",
            "description": "Edits by course code. Quarters are ids such as 2027-AU "
            "(Autumn 2027) or 2028-WI (Winter 2028).",
            "items": _obj(
                {
                    "op": {"type": "string", "enum": ["add", "move", "remove"]},
                    "course": {"type": "string"},
                    "term": {
                        **_NULLABLE_STR,
                        "description": "add: the quarter; remove: the quarter (optional)",
                    },
                    "from_term": {**_NULLABLE_STR, "description": "move: from (optional)"},
                    "to_term": {**_NULLABLE_STR, "description": "move: to"},
                }
            ),
        }
    }
)


@dataclass
class Proposal:
    ops: list[ChangeOp]
    report: Report
    base_plan_hash: str


@dataclass
class ToolBox:
    """The tools of one run, bound to the student's plan (read-only)."""

    db: Session
    state: PlanState
    report: Report
    statuses: tuple[str, ...]
    show_unpublished: bool
    proposals: list[Proposal] = field(default_factory=list)
    #: Forum posts and summaries need login (decision 6): a logged-out run gets no forum tools.
    logged_in: bool = False

    @property
    def year(self) -> str:
        return self.state.catalog_year

    # -------------------------------------------------------------- catalog

    def search_courses(self, args: dict[str, Any]) -> ToolOutput:
        level = args.get("level")
        items, total = catalog_repo.search_courses(
            self.db,
            self.year,
            q=args.get("query") or None,
            subject=args.get("subject") or None,
            level=level if level in range(10000, 100000, 10000) else None,
            quarter=args.get("quarter") or None,
            core_tag=args.get("core_tag") or None,
            max_workload_hours=args.get("max_workload_hours"),
            limit=MAX_RESULTS,
        )
        ids: set[str] = set()
        rows = []
        for c in items:
            attrs, attr_ids = _attrs(c.code, c.attributes)
            ids |= attr_ids | {f"course:{c.code}"}
            rows.append(
                {
                    "code": c.code,
                    "title": c.title,
                    "units": c.units,
                    "core_tags": c.core_tags,
                    "tags": c.tags[:6],
                    "attributes": attrs,
                }
            )
        return ToolOutput(to_json({"total": total, "courses": rows}), frozenset(ids))

    def _course(self, code: str) -> tuple[dict[str, Any], set[str]]:
        try:
            d = catalog_repo.course_detail(self.db, self.year, code, statuses=self.statuses)
        except catalog_repo.NotFoundError:
            raise ValueError(f"No course {code} in the {self.year} catalog.") from None
        attrs, ids = _attrs(d.code, d.attributes)
        ids.add(f"course:{d.code}")
        description = (d.description or "")[:DESCRIPTION_CHARS]
        return (
            {
                "code": d.code,
                "title": d.title,
                "units": d.units,
                "description": description,
                "prerequisites": d.prereq_human or d.prereq_text,
                "crosslists": d.crosslists,
                "core_tags": d.core_tags,
                "offered": {o.quarter: round(o.p_offered, 2) for o in d.offerings},
                "attributes": attrs,
                "counts_toward": [
                    f"{c.program_name}: {c.label or c.node_id}" for c in d.counts_toward[:8]
                ],
                "unlocks": d.unlocks[:10],
            },
            ids,
        )

    def get_course(self, args: dict[str, Any]) -> ToolOutput:
        data, ids = self._course(str(args["code"]))
        return ToolOutput(to_json(data), frozenset(ids))

    def compare_courses(self, args: dict[str, Any]) -> ToolOutput:
        codes = [str(c) for c in args.get("codes", [])][:4]
        if len(codes) < 2:
            raise ValueError("Give two to four course codes.")
        rows, ids = [], set()
        for code in codes:
            data, found = self._course(code)
            data.pop("description", None)
            data.pop("unlocks", None)
            rows.append(data)
            ids |= found
        return ToolOutput(to_json({"courses": rows}), frozenset(ids))

    def get_program(self, args: dict[str, Any]) -> ToolOutput:
        program_id = str(args["program_id"])
        try:
            d = catalog_repo.program_detail(self.db, self.year, program_id, statuses=self.statuses)
        except catalog_repo.NotFoundError as exc:
            raise ValueError(str(exc)) from None
        progress = [p for p in self.report.progress if p.program_id == program_id]
        data: dict[str, Any] = {"id": d.id, "name": d.name, "type": d.type, "status": d.status}
        if progress:
            data["requirements"] = [
                {
                    "node": p.node_id,
                    "label": p.label,
                    "have": p.have,
                    "need": p.need,
                    "unit": p.unit,
                    "satisfied": p.satisfied,
                    "courses": p.courses,
                }
                for p in progress[:60]
            ]
        else:
            rules = ProgramRules(id=d.id, catalog_year=d.catalog_year, rules=d.rules)
            data["requirements"] = [
                {"node": path, "label": node.label, "kind": node.kind}
                for path, node in list(iter_nodes(rules))[:60]
            ]
            data["note"] = "This program is not in the student's plan; no progress is shown."
        return ToolOutput(to_json(data), frozenset({f"program:{d.id}"}))

    # -------------------------------------------------------------- forum

    def _pages(self, code: str) -> list[tuple[int, str]]:
        """The forum pages of `code`, including the pages it shares with the codes it is
        cross-listed under (P08-5); one per instructor."""
        return [
            (page.id, instructor.display_name) for page, instructor in pages_of_code(self.db, code)
        ]

    def get_forum_summary(self, args: dict[str, Any]) -> ToolOutput:
        code = str(args["code"])
        pages = self._pages(code)
        summaries = {
            s.course_instructor_id: s
            for s in self.db.scalars(
                sa.select(m.ForumSummary).where(
                    m.ForumSummary.course_instructor_id.in_([p for p, _ in pages])
                )
            )
        }
        ids: set[str] = set()
        parts = [f"Forum summaries for {code}:"]
        for page_id, instructor in pages:
            s = summaries.get(page_id)
            if s is None or hidden_citations(self.db, s):
                continue
            ids.add(f"summary:{page_id}")
            parts.append(f"summary:{page_id} · {instructor} · {s.n_posts} posts")
            parts.append(untrusted(f"summary:{page_id}", s.text))
        try:
            attrs, attr_ids = _attrs(code, self._course_attributes(code))
        except ValueError:
            attrs, attr_ids = {}, set()
        ids |= attr_ids
        if attrs:
            parts.append("Course attributes: " + to_json(attrs))
        if len(parts) == 1:
            parts.append("No forum summary yet.")
        return ToolOutput("\n".join(parts), frozenset(ids))

    def _course_attributes(self, code: str) -> list[AttributeValue]:
        items, _ = catalog_repo.search_courses(self.db, self.year, q=code, limit=1)
        return items[0].attributes if items and items[0].code == code else []

    def get_forum_posts(self, args: dict[str, Any]) -> ToolOutput:
        code = str(args["code"])
        limit = max(1, min(int(args.get("limit") or MAX_POSTS), MAX_POSTS))
        pages = dict(self._pages(code))
        if not pages:
            return ToolOutput(f"No forum pages for {code}.")
        query = (
            sa.select(m.Post, m.ReviewRating)
            .outerjoin(m.ReviewRating, m.ReviewRating.post_id == m.Post.id)
            .where(m.Post.course_instructor_id.in_(list(pages)), m.Post.status == "visible")
            .order_by(m.Post.score.desc(), m.Post.id.desc())
            .limit(limit)
        )
        kind = args.get("kind")
        if kind in ("review", "discussion"):
            query = query.where(m.Post.kind == kind)
        parts, ids = [f"Forum posts for {code}:"], set()
        for post, rating in self.db.execute(query).all():
            ids.add(f"post:{post.id}")
            head = [f"post:{post.id}", post.kind, pages[post.course_instructor_id]]
            if post.term_taken:
                head.append(f"taken {post.term_taken}")
            head.append(f"score {post.score}")
            if rating is not None:
                head.append(
                    f"overall {rating.overall}/5, difficulty {rating.difficulty}/5, "
                    f"{rating.workload_hours:g} h/wk, "
                    f"{'recommends' if rating.would_recommend else 'does not recommend'}"
                )
            body = (f"{post.title}\n" if post.title else "") + post.body_md[:POST_CHARS]
            parts.append(" · ".join(head))
            parts.append(untrusted(f"post:{post.id}", body))
        if len(parts) == 1:
            parts.append("No visible posts.")
        return ToolOutput("\n".join(parts), frozenset(ids))

    # -------------------------------------------------------------- plan

    def get_plan(self, args: dict[str, Any]) -> ToolOutput:
        quarters: dict[str, list[dict[str, Any]]] = {}
        ids: set[str] = set()
        for item in sorted(self.state.items, key=lambda i: term_key(i.term)):
            entry: dict[str, Any] = {"status": item.status}
            if item.course:
                entry["course"] = item.course
                ids.add(f"course:{item.course}")
            else:
                entry["placeholder_for"] = item.slot_ref
            if item.locked:
                entry["locked"] = True
            quarters.setdefault(item.term, []).append(entry)
        ids |= {f"program:{p.program_id}" for p in self.state.programs}
        data = {
            "catalog_year": self.state.catalog_year,
            "entry_term": self.state.entry_term,
            "programs": [p.program_id for p in self.state.programs],
            "goals": [g.model_dump(mode="json", exclude_none=True) for g in self.state.goals],
            "quarters": quarters,
            "verifier": {
                "status": self.report.status,
                "issues": [
                    {"code": i.code, "level": i.level, "message": i.message}
                    for i in self.report.issues[:15]
                ],
            },
        }
        return ToolOutput(to_json(data), frozenset(ids))

    def _preview(self, args: dict[str, Any]) -> tuple[list[ChangeOp], Report]:
        try:
            ops = [o.to_op() for o in OpsIn.model_validate(args).ops]
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid edits: {exc}") from None
        try:
            after = apply_ops(self.state, ops)
        except ChangeOpError as exc:
            raise ValueError(f"These edits do not fit the plan: {exc}") from None
        try:
            rules, catalog = load_verify_inputs(
                self.db, after, show_unpublished=self.show_unpublished
            )
        except UnknownProgramsError as exc:
            raise ValueError(f"Unknown program(s): {exc.program_ids}") from None
        report, _ = verify_checked(after, rules, catalog)
        return ops, report

    def _verdict(self, report: Report) -> dict[str, Any]:
        before = {(i.code, i.message) for i in self.report.issues}
        return {
            "status_after": report.status,
            "status_before": self.report.status,
            "new_issues": [
                {"code": i.code, "level": i.level, "message": i.message}
                for i in report.issues
                if (i.code, i.message) not in before
            ][:10],
            "resolved_issues": len(before - {(i.code, i.message) for i in report.issues}),
        }

    def preview_ops(self, args: dict[str, Any]) -> ToolOutput:
        _, report = self._preview(args)
        return ToolOutput(to_json(self._verdict(report)))

    def propose_change_set(self, args: dict[str, Any]) -> ToolOutput:
        if len(self.proposals) >= MAX_PROPOSALS:
            raise ValueError("You already proposed the most changes allowed in one answer.")
        ops, report = self._preview(args)
        self.proposals.append(Proposal(ops, report, plan_hash(self.state)))
        verdict = self._verdict(report)
        verdict["proposal"] = f"p{len(self.proposals)}"
        verdict["note"] = (
            "The student sees a proposal card. Nothing is applied until they click Apply or "
            "type a confirmation."
        )
        return ToolOutput(to_json(verdict))

    def change_sets(self) -> list[ChangeSet]:
        return [
            ChangeSet(
                origin="chat", ops=p.ops, base_plan_hash=p.base_plan_hash, preview_report=p.report
            )
            for p in self.proposals
        ]

    def tools(self, names: Sequence[str]) -> list[Tool]:
        allowed = [n for n in names if self.logged_in or n not in FORUM_TOOLS]
        return [TOOLS[name](self) for name in allowed]


TOOLS: dict[str, Any] = {
    "search_courses": lambda box: Tool(
        "search_courses",
        "Search the catalog. Every filter is optional (null). Returns up to 10 courses with "
        "their attributes (workload_hours, difficulty, recommend_rate, ... with sample size n).",
        _obj(
            {
                "query": {**_NULLABLE_STR, "description": "Words in the code or title"},
                "subject": {**_NULLABLE_STR, "description": "e.g. CMSC"},
                "level": {"type": ["integer", "null"], "description": "10000, 20000, ..."},
                "quarter": {"type": ["string", "null"], "enum": ["AU", "WI", "SP", "SU", None]},
                "core_tag": {**_NULLABLE_STR, "description": "A Core area, e.g. huma"},
                "max_workload_hours": {"type": ["number", "null"]},
            }
        ),
        box.search_courses,
    ),
    "get_course": lambda box: Tool(
        "get_course",
        "One course: description, prerequisites, usual quarters (probability offered), "
        "attributes and the requirements it can fill.",
        _obj({"code": _CODE}),
        box.get_course,
    ),
    "compare_courses": lambda box: Tool(
        "compare_courses",
        "Two to four courses side by side: attributes, prerequisites and usual quarters.",
        _obj({"codes": {"type": "array", "items": {"type": "string"}}}),
        box.compare_courses,
    ),
    "get_program": lambda box: Tool(
        "get_program",
        "A program's requirements; for a program in the plan, the plan's progress on each.",
        _obj({"program_id": {"type": "string", "description": "e.g. cmsc-bs"}}),
        box.get_program,
    ),
    "get_forum_summary": lambda box: Tool(
        "get_forum_summary",
        "What students say about a course (summaries per instructor) and its attributes.",
        _obj({"code": _CODE}),
        box.get_forum_summary,
    ),
    "get_forum_posts": lambda box: Tool(
        "get_forum_posts",
        "Up to 5 visible forum posts about a course, highest scored first.",
        _obj(
            {
                "code": _CODE,
                "kind": {"type": ["string", "null"], "enum": ["review", "discussion", None]},
                "limit": {"type": ["integer", "null"]},
            }
        ),
        box.get_forum_posts,
    ),
    "get_plan": lambda box: Tool(
        "get_plan",
        "The student's plan: courses by quarter, programs, goals and the verifier's issues.",
        _obj({}),
        box.get_plan,
    ),
    "preview_ops": lambda box: Tool(
        "preview_ops",
        "Run the verifier on hypothetical edits. Saves nothing.",
        _OPS_SCHEMA,
        box.preview_ops,
    ),
    "propose_change_set": lambda box: Tool(
        "propose_change_set",
        "Show the student a proposal card for these edits, with the verifier's verdict. "
        "Nothing is applied: only the student can apply it.",
        _OPS_SCHEMA,
        box.propose_change_set,
    ),
}

#: Tools that read forum posts or summaries: only for logged-in callers.
FORUM_TOOLS = frozenset({"get_forum_summary", "get_forum_posts"})
A1_TOOLS = ("search_courses", "get_course", "get_forum_summary")
A1_RATIONALE_TOOLS = ("get_course", "get_forum_summary")
#: The advisor's tools: reads, plus one draft tool. No tool applies anything.
A2_TOOLS = (
    "get_plan",
    "preview_ops",
    "search_courses",
    "get_course",
    "get_program",
    "get_forum_summary",
    "get_forum_posts",
    "compare_courses",
    "propose_change_set",
)
