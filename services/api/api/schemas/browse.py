"""The Catalog page's browse rows (`GET /catalog/browse`) and the course rating summaries
(`GET /course-ratings`), issue #19.

Every course an item names exists in the catalog: the codes come from the database or from the
hand-written list `data/catalog/new_courses.yaml`, never from a model.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from api.schemas.catalog import RatingSummary


class FeedCategoryRef(BaseModel):
    """A family of subjects (`api.feed.categories`), with the motif of its generated art."""

    key: str
    label: str
    motif: str


class CourseRef(BaseModel):
    code: str
    title: str


class Illustration(BaseModel):
    """Inputs of the page's generated SVG art (no image is fetched)."""

    seed: int = Field(ge=0)
    motif: str
    palette: int = Field(ge=0, le=5)


class CourseStats(BaseModel):
    """From `attribute_value` (forum reviews and estimates), when there are any."""

    workload_hours: float | None = None
    difficulty: float | None = None
    n: int = 0


class CourseItem(BaseModel):
    """A course spotlight."""

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
    illustration: Illustration
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


class NewCourse(BaseModel):
    """A newly released course. `basis` says how it is known to be new: `listed` (a person put
    it in `data/catalog/new_courses.yaml`, with the quote that says so) or `catalog` (it is in
    this catalog year and was not in the one before)."""

    code: str
    title: str
    units: int
    core_tags: list[str] = []
    #: At most 300 characters of the catalog description, cut at a word.
    excerpt: str = ""
    basis: Literal["listed", "catalog"]
    #: One short line on why it counts as new ("Not in the 2025-26 catalog").
    reason: str
    source_url: str | None = None
    source_quote: str | None = None


class CatalogBrowse(BaseModel):
    """The rows the Catalog page shows before the student searches. Any row may be empty."""

    catalog_year: str | None
    new_courses: list[NewCourse] = []
    spotlights: list[CourseItem] = []
    #: Newest first. Forum reviews and discussions only for a logged-in reader.
    quotes: list[CommentItem] = []


class CourseRatings(BaseModel):
    """Student ratings pooled over every instructor's page of each course (logged in only).
    A course with no visible review has `n_reviews` 0."""

    ratings: dict[str, RatingSummary]
