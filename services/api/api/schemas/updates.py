"""What is new for the student (`/me/updates`), shown by the dashboard's "What's new" card."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

UpdateKind = Literal["thread", "reply", "review", "discussion", "comment"]


class UpdateItem(BaseModel):
    """One new thing on Quarterly that concerns the student. Text is plain (no markdown) and
    scrubbed of emails and phone numbers; `href` is a path on this site."""

    kind: UpdateKind
    #: The id in its own table (commons_thread, commons_reply, post or comment).
    id: int
    title: str
    snippet: str
    course_code: str | None = None
    href: str
    day: dt.date
    #: Why it is shown: "On a thread you follow", "Matches your interest in ...".
    reason: str
    #: Newer than the student's high-water mark (POST /me/updates/seen).
    is_new: bool


class UpdatesOut(BaseModel):
    #: Newest first, at most 30.
    items: list[UpdateItem] = []
    #: How many of `items` are new.
    unread: int = 0


class UpdatesSeen(BaseModel):
    """High-water marks: the newest id the student has seen of each kind of item. In a request
    a missing mark means "the newest there is now"; marks never move backwards."""

    thread: int | None = Field(default=None, ge=0)
    reply: int | None = Field(default=None, ge=0)
    post: int | None = Field(default=None, ge=0)
    comment: int | None = Field(default=None, ge=0)
