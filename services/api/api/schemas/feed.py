"""The feed's API shapes (`/feed`, `/feed/categories`, `/agents/feed-notes`).

A feed page is a list of items of six kinds (a discriminated union on `kind`), each with a stable
`id` ("course:CMSC 14100", "book:the-odyssey", "comment:commons:12", "comment:post:7",
"words:math", "program:cmsc-bs", "question:31"). Every course an item names exists in the
catalog: the codes come from the database, never from a model.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, Field

FeedTab = Literal["for_you", "explore", "following"]


class FeedCategoryRef(BaseModel):
    key: str
    label: str
    motif: str


class FeedCategory(FeedCategoryRef):
    blurb: str
    #: The catalog subjects in this category (codes such as "MATH").
    subjects: list[str]
    #: How many feed-worthy courses the category has this catalog year.
    course_count: int


class FeedCategories(BaseModel):
    categories: list[FeedCategory]
    #: The logged-in student's saved focus (profile `feed_categories`); empty when logged out.
    selected: list[str]


class CourseRef(BaseModel):
    code: str
    title: str


class Illustration(BaseModel):
    """Inputs of the page's generated SVG art (no image is fetched)."""

    seed: int = Field(ge=0)
    motif: str
    palette: int = Field(ge=0, le=5)


class ShelfBook(BaseModel):
    id: str
    slug: str
    title: str
    author: str
    year: int
    #: What the page shows for the year ("c. 430 BCE", "1835-40", "1962").
    when: str


class CourseStats(BaseModel):
    """From `attribute_value` (forum reviews and estimates), when there are any."""

    workload_hours: float | None = None
    difficulty: float | None = None
    n: int = 0


class CourseItem(BaseModel):
    kind: Literal["course"] = "course"
    id: str
    code: str
    title: str
    subject: str
    category: FeedCategoryRef
    units: int
    #: At most 300 characters of the catalog description, cut at a word.
    excerpt: str
    core_tags: list[str]
    #: 6-10 distinctive words of the title and description (the page's floating words).
    words: list[str]
    illustration: Illustration
    #: At most two books from the Quarterly shelf (reading for the curious, not a syllabus).
    books: list[ShelfBook]
    stats: CourseStats | None = None
    #: Why this course is here, in one short line (deterministic, never written by a model).
    reason: str
    #: Visible Commons threads about this course.
    commons_count: int = 0


class CommentItem(BaseModel):
    """A student's voice about a course: a Commons reply, or (logged in only) a forum post."""

    kind: Literal["comment"] = "comment"
    id: str
    #: Plain text, at most 240 characters, emails and phone numbers scrubbed.
    snippet: str
    course: CourseRef
    category: FeedCategoryRef
    #: The author's pseudonym on that thread or page, or "A student".
    handle: str
    voice: Literal["reply", "review", "discussion"]
    source: Literal["commons", "forum"]
    href: str
    day: dt.date


class BookItem(BaseModel):
    kind: Literal["book"] = "book"
    id: str
    book: ShelfBook
    category: FeedCategoryRef
    #: 2-4 real courses that share the book's themes.
    courses: list[CourseRef]
    reason: str


class WeightedWord(BaseModel):
    text: str
    weight: int = Field(ge=1, le=5)


class WordsItem(BaseModel):
    kind: Literal["words"] = "words"
    id: str
    category: FeedCategoryRef
    label: str
    words: list[WeightedWord]


class ProgramItem(BaseModel):
    kind: Literal["program"] = "program"
    id: str
    program_id: str
    name: str
    type: str
    department: str | None
    reason: str


class QuestionItem(BaseModel):
    """A Commons question that is waiting for an answer, or a recent one."""

    kind: Literal["question"] = "question"
    id: str
    thread_id: int
    title: str
    snippet: str
    course: CourseRef | None
    reply_count: int
    answered: bool
    href: str
    day: dt.date


FeedItem = Annotated[
    CourseItem | CommentItem | BookItem | WordsItem | ProgramItem | QuestionItem,
    Field(discriminator="kind"),
]


class FeedPage(BaseModel):
    tab: FeedTab
    items: list[FeedItem]
    #: Pass back as `cursor` for the next page; null at the end of the feed.
    next_cursor: str | None
    #: The category keys this page was filtered by (the request's, else the saved focus).
    categories_applied: list[str]
    #: A deterministic line for the top of the feed (the AI notes may replace it).
    headline: str
    #: Whether the page used the student's profile (logged in with something to go on).
    personalized: bool


class FeedNotesRequest(BaseModel):
    item_ids: list[Annotated[str, Field(min_length=3, max_length=96)]] = Field(
        min_length=1, max_length=12
    )
    #: The tab and categories of the page the items are on (for the fallback's reasons).
    tab: FeedTab = "for_you"
    categories: str | None = Field(default=None, max_length=400)


class FeedNotes(BaseModel):
    #: At most 90 characters.
    headline: str
    #: Item id -> one line (at most 140 characters) on why the item is in the feed.
    notes: dict[str, str]
    #: True when a model wrote the headline and notes (label them as AI on the page).
    ai: bool
