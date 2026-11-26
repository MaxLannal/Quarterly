"""The campus read tools shared by the campus agents (docs/BEST-OF-UCHICAGO-PLAN.md): the
Commons bot and the dashboard's guide. (The Ask chatbot, the companion and the route drafter
were removed in issue #15.)

`CampusTools(db, account=..., show_unpublished=...)` is built per request; `.tools(names)` gives
the `Tool`s an agent may call. None of them writes anything.

- The advisor's read tools without a plan (`api.agents.live.campus_toolbox`): `search_courses`,
  `get_course`, `compare_courses`, `get_program`, `get_forum_summary`, `get_forum_posts`.
- `list_programs`: majors, minors and other programs by name or department (`program:<id>`).
- `search_commons`: Commons questions (`thread:<id>`), student text wrapped as untrusted.
- `get_profile`: the logged-in student's dashboard profile (never the email).
- `campus_guide`: hand-written notes about College life (`data/campus/guide.yaml`, `guide:<id>`).

Forum tools and `get_profile` need login (decision 6: forum text is for logged-in readers); a
logged-out run never gets them. Every result lists the citable ids it contains.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
import yaml
from llm_gateway.api import Tool, ToolOutput
from llm_gateway.loop import to_json
from sqlalchemy.orm import Session

from api.agents import live
from api.agents.live import campus_toolbox, default_label
from api.agents.tools import TOOLS as BOX_TOOL_FACTORIES
from api.agents.tools import untrusted
from api.db import models as m
from api.repo import catalog as catalog_repo

#: Every tool name `CampusTools.tools` knows, in the order agents usually list them.
CAMPUS_TOOLS: tuple[str, ...] = (
    "search_courses",
    "get_course",
    "compare_courses",
    "get_program",
    "list_programs",
    "get_forum_summary",
    "get_forum_posts",
    "search_commons",
    "get_profile",
    "campus_guide",
)
#: The advisor's tools, served by `campus_toolbox`.
BOX_TOOLS = frozenset(
    {
        "search_courses",
        "get_course",
        "compare_courses",
        "get_program",
        "get_forum_summary",
        "get_forum_posts",
    }
)
#: Tools that need a logged-in account.
LOGIN_TOOLS = frozenset({"get_forum_summary", "get_forum_posts", "get_profile"})

MAX_PROGRAMS = 25
MAX_THREADS = 8
THREAD_BODY_CHARS = 600
BOT_CHARS = 300
MAX_GUIDE = 3
#: Words that say nothing about what a search is for.
# fmt: off
STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "best", "by", "can", "course", "courses",
        "class", "classes", "do", "does", "for", "from", "good", "how", "i", "in", "into",
        "is", "it", "its", "me", "my", "of", "on", "or", "should", "take", "the", "their",
        "there", "this", "to", "what", "when", "where", "which", "who", "why", "will", "with",
        "would", "you", "your", "about", "any", "some", "get", "uchicago", "chicago", "tell",
        "know", "want", "need", "like", "think", "please", "help", "much", "many", "more",
        "interested", "first-year", "student", "students", "taking", "start", "starting",
        "suits", "suit", "someone", "loves", "love", "fit", "fits", "really", "great",
    }
)
# fmt: on


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_NULLABLE_STR = {"type": ["string", "null"]}


def keywords(text: str, limit: int = 6) -> list[str]:
    """The content words of `text` (lower case, no stopwords, at least 3 letters), in order."""
    words: list[str] = []
    for word in re.findall(r"[a-z0-9][a-z0-9'\-]*", text.lower()):
        word = word.strip("'-")
        if len(word) >= 3 and word not in STOPWORDS and word not in words:
            words.append(word)
    return words[:limit]


# ------------------------------------------------------------------------------ campus guide


@dataclass(frozen=True)
class GuideEntry:
    id: str
    title: str
    keywords: tuple[str, ...]
    text: str
    source_url: str


def guide_path() -> Path:
    """`CAMPUS_GUIDE` if set, else `data/campus/guide.yaml` above this file or the working
    directory (the repository root; `/app/data` in the API image)."""
    explicit = os.environ.get("CAMPUS_GUIDE")
    if explicit:
        return Path(explicit)
    for base in (Path(__file__).resolve(), Path.cwd()):
        for folder in (base, *base.parents):
            candidate = folder / "data" / "campus" / "guide.yaml"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("data/campus/guide.yaml not found (set CAMPUS_GUIDE)")


@lru_cache
def load_guide() -> tuple[GuideEntry, ...]:
    raw = yaml.safe_load(guide_path().read_text(encoding="utf-8")) or {}
    entries = []
    for item in raw.get("entries", []):
        url = str(item["source_url"])
        host = urlparse(url).hostname or ""
        if not url.startswith("https://") or not (
            host == "uchicago.edu" or host.endswith(".uchicago.edu")
        ):
            raise ValueError(f"guide entry {item.get('id')}: source_url must be on uchicago.edu")
        entries.append(
            GuideEntry(
                id=str(item["id"]),
                title=str(item["title"]),
                keywords=tuple(str(k).lower() for k in item.get("keywords", [])),
                text=" ".join(str(item["text"]).split()),
                source_url=url,
            )
        )
    return tuple(entries)


def guide_entry(entry_id: str) -> GuideEntry | None:
    return next((e for e in load_guide() if e.id == entry_id), None)


def search_guide(topic: str, limit: int = MAX_GUIDE) -> list[GuideEntry]:
    """Guide entries about `topic`, best first: a keyword phrase in the topic counts most, then
    topic words in the title, the keywords and the text."""
    text = " ".join(topic.lower().split())
    words = keywords(text, limit=10)
    scored: list[tuple[float, int, GuideEntry]] = []
    for index, entry in enumerate(load_guide()):
        score = 0.0
        for phrase in entry.keywords:
            if re.search(rf"\b{re.escape(phrase)}", text):
                score += 3 + phrase.count(" ")
        title = entry.title.lower()
        body = entry.text.lower()
        kw = " ".join(entry.keywords)
        for word in words:
            stem = word[:-1] if len(word) > 4 and word.endswith("s") else word
            if stem in title:
                score += 2
            if stem in kw:
                score += 1.5
            if stem in body:
                score += 0.5
        if score >= 1.5:
            scored.append((score, index, entry))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [entry for _, _, entry in scored[:limit]]


# ------------------------------------------------------------------------------ the tools


class CampusTools:
    """The read tools of one campus-agent run, bound to the request's account (or none)."""

    def __init__(self, db: Session, *, account: m.Account | None, show_unpublished: bool) -> None:
        self.db = db
        self.account = account
        self.show_unpublished = show_unpublished
        self.statuses = catalog_repo.ALL_STATUSES if show_unpublished else catalog_repo.PUBLISHED
        self.box = campus_toolbox(
            db, logged_in=account is not None, show_unpublished=show_unpublished
        )

    @property
    def logged_in(self) -> bool:
        return self.account is not None

    def available(self, names: Sequence[str]) -> list[str]:
        """`names` without the ones this caller may not use (login-only tools when logged out)."""
        return [n for n in names if n in CAMPUS_TOOLS and (self.logged_in or n not in LOGIN_TOOLS)]

    def tools(self, names: Sequence[str]) -> list[Tool]:
        out: list[Tool] = []
        for name in self.available(names):
            if name in BOX_TOOLS:
                out.append(BOX_TOOL_FACTORIES[name](self.box))
            else:
                out.append(_OWN_TOOLS[name](self))
        return out

    # ---------------------------------------------------------------- programs

    def list_programs(self, args: dict[str, Any]) -> ToolOutput:
        query = " ".join(str(args.get("query") or "").split()).lower()
        kind = str(args.get("type") or "").strip().lower() or None
        programs = catalog_repo.list_programs(
            self.db, live.CAMPUS_YEAR, program_type=kind, statuses=self.statuses
        )
        words = keywords(query) if query else []
        rows = []
        for p in programs:
            hay = f"{p.id} {p.name} {p.department or ''} {p.type}".lower()
            if query and query not in hay and not (words and all(w in hay for w in words)):
                continue
            rows.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "type": p.type,
                    "degree": p.degree,
                    "department": p.department,
                }
            )
        if not rows and words:  # nothing had every word: any word
            for p in programs:
                hay = f"{p.id} {p.name} {p.department or ''}".lower()
                if any(w in hay for w in words):
                    rows.append(
                        {
                            "id": p.id,
                            "name": p.name,
                            "type": p.type,
                            "degree": p.degree,
                            "department": p.department,
                        }
                    )
        rows = rows[:MAX_PROGRAMS]
        data: dict[str, Any] = {"total": len(rows), "programs": rows}
        if not rows:
            data["note"] = (
                "No program in Quarterly's catalog matches. Quarterly holds only some of the "
                "College's programs; the College Catalog lists them all."
            )
        return ToolOutput(to_json(data), frozenset(f"program:{r['id']}" for r in rows))

    # ---------------------------------------------------------------- the Commons

    def search_commons(self, args: dict[str, Any]) -> ToolOutput:
        query = " ".join(str(args.get("query") or "").split())[:200]
        thread = m.CommonsThread
        stmt = (
            sa.select(thread, m.Course.code)
            .outerjoin(m.Course, m.Course.id == thread.course_id)
            .where(thread.status == "visible")
            .order_by(thread.id.desc())
            .limit(MAX_THREADS)
        )
        words = keywords(query, limit=5)
        if words:

            def hit(word: str) -> sa.ColumnElement[bool]:
                return sa.or_(
                    thread.title.icontains(word, autoescape=True),
                    thread.body_md.icontains(word, autoescape=True),
                    sa.func.coalesce(m.Course.code, "").icontains(word, autoescape=True),
                )

            rows = self.db.execute(stmt.where(sa.and_(*(hit(w) for w in words)))).all()
            if not rows and len(words) > 1:
                rows = self.db.execute(stmt.where(sa.or_(*(hit(w) for w in words)))).all()
        else:
            rows = self.db.execute(stmt).all()
        if not rows:
            return ToolOutput(to_json({"threads": [], "note": "No forum questions match."}))
        bots = self._bot_answers([t.id for t, _ in rows])
        parts = [f"Forum questions matching “{query}” (newest first):" if query else "Newest:"]
        ids: set[str] = set()
        for t, code in rows:
            ids.add(f"thread:{t.id}")
            head = [f"thread:{t.id}", f"{t.reply_count} replies", f"score {t.score}"]
            if code:
                head.append(f"about {code}")
                ids.add(f"course:{code}")
            parts.append(" · ".join(head))
            body = f"{t.title}\n{t.body_md[:THREAD_BODY_CHARS]}".strip()
            parts.append(untrusted(f"thread:{t.id}", body))
            if t.id in bots:
                parts.append(untrusted(f"thread:{t.id}", "Bot answer: " + bots[t.id][:BOT_CHARS]))
        return ToolOutput("\n".join(parts), frozenset(ids))

    def _bot_answers(self, thread_ids: list[int]) -> dict[int, str]:
        rows = self.db.execute(
            sa.select(m.CommonsReply.thread_id, m.CommonsReply.body_md)
            .where(
                m.CommonsReply.thread_id.in_(thread_ids),
                m.CommonsReply.kind == "bot",
                m.CommonsReply.status == "visible",
            )
            .order_by(m.CommonsReply.id)
        ).all()
        return {tid: body for tid, body in rows}

    # ---------------------------------------------------------------- the student

    def get_profile(self, args: dict[str, Any]) -> ToolOutput:
        if self.account is None:
            raise ValueError("The student is not logged in.")
        profile = self.db.get(m.StudentProfile, self.account.id)
        if profile is None:
            return ToolOutput(
                to_json(
                    {
                        "profile": None,
                        "note": "The student has not filled in a dashboard yet (/me).",
                    }
                )
            )
        ids: set[str] = set()
        known_programs = {
            p.id
            for p in catalog_repo.list_programs(self.db, live.CAMPUS_YEAR, statuses=self.statuses)
        }
        programs = [p for p in profile.intended_programs if p in known_programs]
        ids |= {f"program:{p}" for p in programs}
        facts = {
            "class_year": profile.class_year,
            "post_grad_plan": profile.post_grad_plan,
            "pace": profile.pace,
            "course_load": profile.course_load,
            "intended_programs": programs,
        }
        words = {"research_areas": profile.research_areas}
        words = {k: v for k, v in words.items() if v}
        parts = ["The student's dashboard profile:", to_json(facts)]
        if words:
            parts.append(untrusted("profile", to_json(words)))
        return ToolOutput("\n".join(parts), frozenset(ids))

    # ---------------------------------------------------------------- campus guide

    def campus_guide(self, args: dict[str, Any]) -> ToolOutput:
        topic = " ".join(str(args.get("topic") or "").split())[:200]
        found = search_guide(topic) if topic else []
        if not found:
            return ToolOutput(
                to_json(
                    {
                        "entries": [],
                        "note": "No guide entry matches. Topics: "
                        + "; ".join(e.title for e in load_guide()),
                    }
                )
            )
        rows = [
            {"id": f"guide:{e.id}", "title": e.title, "text": e.text, "source": e.source_url}
            for e in found
        ]
        return ToolOutput(to_json({"entries": rows}), frozenset(f"guide:{e.id}" for e in found))


def label(tool: str, args: dict[str, Any]) -> str:
    """Step labels for `run_live` (the live trace): a little more specific than the default."""

    def arg(name: str) -> str:
        return str(args.get(name) or "").strip()[:60]

    if tool == "search_courses" and not (arg("query") or arg("q")):
        tag = arg("core_tag").removeprefix("core:").replace("_", " ")
        if tag:
            return f"Searching the catalog for {tag} Core courses"
        if arg("subject"):
            return f"Searching {arg('subject').upper()} courses"
    if tool == "list_programs" and arg("query"):
        return f"Looking through programs for “{arg('query')}”"
    if tool == "search_commons" and arg("query"):
        return f"Searching forum questions about “{arg('query')}”"
    if tool == "campus_guide" and arg("topic"):
        return f"Checking the campus guide on “{arg('topic')}”"
    if tool == "get_program" and arg("program_id"):
        return f"Reading the requirements of {arg('program_id')}"
    return default_label(tool, args)


_OWN_TOOLS: dict[str, Any] = {
    "list_programs": lambda t: Tool(
        "list_programs",
        "Majors, minors and other programs in Quarterly's catalog whose name or department "
        "matches `query` (null: all). Returns ids for get_program.",
        _obj(
            {
                "query": {**_NULLABLE_STR, "description": "e.g. computer science, economics"},
                "type": {
                    **_NULLABLE_STR,
                    "description": "major, minor, specialization, core, ... (null: any)",
                },
            }
        ),
        t.list_programs,
    ),
    "search_commons": lambda t: Tool(
        "search_commons",
        "Questions students asked in Quarterly's forum (the Commons), newest first, with the "
        "forum bot's answer when there is one.",
        _obj({"query": {"type": "string", "description": "Words to look for"}}),
        t.search_commons,
    ),
    "get_profile": lambda t: Tool(
        "get_profile",
        "The student's own dashboard profile: class year, intended programs, plan after "
        "graduation, pace, course load and research areas.",
        _obj({}),
        t.get_profile,
    ),
    "campus_guide": lambda t: Tool(
        "campus_guide",
        "Hand-written notes about College life (the Core, the quarter system, advising, "
        "libraries, registration, study abroad, careers, research, housing, Hyde Park), each "
        "with an official uchicago.edu source.",
        _obj({"topic": {"type": "string", "description": "e.g. core humanities, libraries"}}),
        t.campus_guide,
    ),
}

__all__ = [
    "BOX_TOOLS",
    "CAMPUS_TOOLS",
    "LOGIN_TOOLS",
    "CampusTools",
    "GuideEntry",
    "guide_entry",
    "keywords",
    "label",
    "load_guide",
    "search_guide",
]
