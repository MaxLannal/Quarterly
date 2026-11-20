"""The Commons (`/commons/*`, docs/BEST-OF-UCHICAGO-PLAN.md): questions about courses, the bot's
answer, nested replies, votes, presence and reports. Dates are day-level only."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, RootModel, field_validator, model_validator

Vote = Literal[-1, 0, 1]
Status = Literal["visible", "removed", "deleted"]
BotState = Literal["pending", "answered", "failed", "off"]
Sort = Literal["hot", "new", "top", "unanswered", "active"]
TargetType = Literal["thread", "reply"]

TITLE_MIN = 8
TITLE_MAX = 160
BODY_MAX = 8000
TAGS_MAX = 5
TAG_MAX = 24
_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def normalize_tags(raw: list[str]) -> list[str]:
    """Lowercase slugs ("Study Abroad" -> "study-abroad"), deduplicated, order kept. Raises
    ValueError for a tag that is not a slug of at most 24 characters, or more than 5 tags."""
    out: list[str] = []
    for tag in raw:
        slug = re.sub(r"[\s_]+", "-", tag.strip().lower()).strip("-")
        if not slug:
            continue
        if len(slug) > TAG_MAX or not _TAG.match(slug):
            raise ValueError(f"tags are lowercase words or slugs of at most {TAG_MAX} characters")
        if slug not in out:
            out.append(slug)
    if len(out) > TAGS_MAX:
        raise ValueError(f"at most {TAGS_MAX} tags")
    return out


class CommonsCourse(BaseModel):
    code: str
    title: str


class CommonsCitation(BaseModel):
    """A source the bot relied on. The web links `course` to /courses/<id>, `program` to
    /programs/<id>, `thread` to /forum/t/<id>; `guide` carries the official `url`."""

    kind: Literal["course", "program", "thread", "guide", "post", "summary", "attribute"]
    id: str
    label: str
    url: str | None = None


class CommonsThreadSummary(BaseModel):
    id: int
    title: str
    #: Plain text, at most 200 characters.
    excerpt: str
    course: CommonsCourse | None = None
    tags: list[str] = []
    score: int
    #: Human answers and comments (the bot's replies are not counted).
    reply_count: int
    #: Human answers (top-level replies).
    answer_count: int
    #: The asker accepted a reply, or a person answered.
    answered: bool
    accepted: bool = False
    bot_state: BotState
    has_bot_answer: bool
    #: The asker's handle on this thread ("Quiet Heron"), or "[deleted account]".
    handle: str
    is_mine: bool = False
    my_vote: Vote = 0
    status: Status = "visible"
    created_day: dt.date
    edited_day: dt.date | None = None


class CommonsThreadList(BaseModel):
    items: list[CommonsThreadSummary]
    #: Pass back as `cursor` for the next page; null on the last page.
    next_cursor: str | None = None
    total: int


class CommonsThreadCreate(BaseModel):
    title: str = Field(min_length=TITLE_MIN, max_length=TITLE_MAX)
    body_md: str = Field(default="", max_length=BODY_MAX)
    #: A course code such as "CMSC 14100"; it must exist in the catalog.
    course_code: str | None = Field(default=None, max_length=16)
    tags: list[Annotated[str, Field(max_length=40)]] = Field(default=[], max_length=12)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)

    @model_validator(mode="after")
    def _title(self) -> Self:
        if len(self.title.strip()) < TITLE_MIN:
            raise ValueError(f"the title needs at least {TITLE_MIN} characters")
        return self


class CommonsThreadUpdate(BaseModel):
    """Only the fields sent change. `course_code: null` detaches the course."""

    title: str | None = Field(default=None, min_length=TITLE_MIN, max_length=TITLE_MAX)
    body_md: str | None = Field(default=None, max_length=BODY_MAX)
    course_code: str | None = Field(default=None, max_length=16)
    tags: list[Annotated[str, Field(max_length=40)]] | None = Field(default=None, max_length=12)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_tags(value)


class CommonsReply(BaseModel):
    id: int
    parent_id: int | None = None
    depth: int
    kind: Literal["human", "bot"]
    #: "Quarterly AI" for the bot.
    handle: str
    #: Written by the asker.
    is_op: bool = False
    is_mine: bool = False
    #: Sanitized on the server; "[deleted]" for a tombstone.
    body_html: str
    #: Only on the reader's own replies (for editing).
    body_md: str | None = None
    citations: list[CommonsCitation] = []
    score: int
    my_vote: Vote = 0
    accepted: bool = False
    status: Status = "visible"
    created_day: dt.date
    edited_day: dt.date | None = None
    children: list[CommonsReply] = []


class CommonsThreadDetail(CommonsThreadSummary):
    body_html: str
    #: Only for the asker (for editing).
    body_md: str | None = None
    #: Real catalog courses the question mentions, in order.
    mentions: list[CommonsCourse] = []
    following: bool = False
    accepted_reply_id: int | None = None
    #: The newest reply's id (for the live "new replies" banner).
    last_reply_id: int | None = None
    #: A tree: top-level replies (the bot's answer first, then by score), each with children.
    replies: list[CommonsReply] = []


class CommonsReplyCreate(BaseModel):
    body_md: str = Field(min_length=1, max_length=BODY_MAX)
    parent_id: int | None = None

    @model_validator(mode="after")
    def _not_blank(self) -> Self:
        if not self.body_md.strip():
            raise ValueError("the reply is empty")
        return self


class CommonsReplyUpdate(BaseModel):
    body_md: str = Field(min_length=1, max_length=BODY_MAX)

    @model_validator(mode="after")
    def _not_blank(self) -> Self:
        if not self.body_md.strip():
            raise ValueError("the reply is empty")
        return self


class CommonsReplyPosted(BaseModel):
    reply: CommonsReply
    #: The reply mentions @quarterly or @ai: the client then calls POST .../bot with
    #: `reply_to` set to this reply.
    summon_bot: bool = False
    reply_count: int


class CommonsVoteIn(BaseModel):
    target_type: TargetType
    target_id: int
    #: 0 withdraws the vote.
    value: Vote


class CommonsVoteOut(BaseModel):
    score: int
    my_vote: Vote


class CommonsAcceptIn(BaseModel):
    #: null takes the acceptance back.
    reply_id: int | None = None


class CommonsAcceptOut(BaseModel):
    accepted_reply_id: int | None = None


class CommonsFollowIn(BaseModel):
    follow: bool


class CommonsFollowOut(BaseModel):
    following: bool


class CommonsPresence(BaseModel):
    #: Other readers typing a reply right now (the caller is never counted).
    typing: int
    latest_reply_id: int | None = None
    reply_count: int
    score: int
    bot_state: BotState


class CommonsReportIn(BaseModel):
    target_type: TargetType
    target_id: int
    reason: str = Field(min_length=1, max_length=500)


class CommonsReportOut(BaseModel):
    id: int
    status: Literal["open", "closed"]


class CommonsBotRequest(BaseModel):
    #: Write the answer again (the asker only).
    regenerate: bool = False
    #: A reply that summoned the bot with @quarterly; the answer is nested under it.
    reply_to: int | None = None


class CommonsStepEvent(BaseModel):
    type: Literal["step"] = "step"
    tool: str
    label: str
    status: Literal["started", "done", "failed"]


class CommonsAnswerEvent(BaseModel):
    type: Literal["answer"] = "answer"
    reply: CommonsReply
    #: True when the AI was off and the answer was built from a catalog search.
    fallback: bool = False


class CommonsBusyEvent(BaseModel):
    """Another reader's request is already writing this answer: poll the thread."""

    type: Literal["busy"] = "busy"
    message: str


class CommonsDoneEvent(BaseModel):
    type: Literal["done"] = "done"


class CommonsErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class CommonsBotEvent(
    RootModel[
        Annotated[
            CommonsStepEvent
            | CommonsAnswerEvent
            | CommonsBusyEvent
            | CommonsDoneEvent
            | CommonsErrorEvent,
            Field(discriminator="type"),
        ]
    ]
):
    """One Server-Sent Event of POST /commons/threads/{thread_id}/bot."""


# ------------------------------------------------------------- moderation (OPEN_QUESTIONS CC-7)


class CommonsModerationReport(BaseModel):
    reason: str
    created_day: dt.date


class CommonsModerationItem(BaseModel):
    """A reported Commons question or reply in the admin's queue."""

    target_type: TargetType
    target_id: int
    title: str
    excerpt: str
    status: Literal["visible", "removed", "deleted"]
    #: The AI's answer (a bot reply), not a student's words.
    by_ai: bool = False
    course_code: str | None = None
    href: str
    reports: list[CommonsModerationReport]


class CommonsModerationDecision(BaseModel):
    decision: Literal["remove", "keep"]
    note: str | None = Field(default=None, max_length=500)


class CommonsModerationResult(BaseModel):
    target_type: TargetType
    target_id: int
    status: Literal["visible", "removed"]
    reports_closed: int
