"""The forum page `/forum` (issue #20): course reviews and Commons discussions in one list
(`GET /forum/items`), and the statistics and rankings beside it (`GET /forum/stats`).

Reviews (`post` + `review_rating`) and discussions (`commons_thread` + `commons_reply`) keep their
own tables (D2); the list only merges them. Dates are day-level only."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from api.schemas.catalog import InstructorSummary
from api.schemas.commons import CommonsCourse, CommonsThreadSummary

ItemType = Literal["review", "discussion"]
Period = Literal["quarter", "year"]
Vote = Literal[-1, 0, 1]


class ForumReviewItem(BaseModel):
    """A course review in the list. Only logged-in readers get these."""

    type: Literal["review"] = "review"
    #: The post id; the review opens at /courses/{code}/i/{instructor}/t/{id}.
    id: int
    page_id: int
    course: CommonsCourse
    instructor: InstructorSummary
    title: str | None = None
    #: Plain text, at most 200 characters.
    excerpt: str
    #: The reviewer's handle on this course x instructor page ("Quiet Heron").
    handle: str
    term_taken: str | None = None
    overall: int
    difficulty: int
    workload_hours: float
    would_recommend: bool
    score: int
    my_vote: Vote = 0
    is_mine: bool = False
    n_comments: int
    created_day: dt.date
    edited_day: dt.date | None = None


class ForumDiscussionItem(BaseModel):
    """A Commons question in the list, with the AI's short answer under it (D1 option A)."""

    type: Literal["discussion"] = "discussion"
    thread: CommonsThreadSummary
    #: The AI's answer (at most 60 words, sanitized HTML), shown labelled as written by an AI;
    #: null until the AI has answered.
    ai_answer_html: str | None = None


ForumItem = Annotated[ForumReviewItem | ForumDiscussionItem, Field(discriminator="type")]


class ForumItemList(BaseModel):
    items: list[ForumItem]
    #: Pass back as `cursor` for the next page; null on the last page.
    next_cursor: str | None = None
    #: Items that match the filters (reviews only when the reader is logged in).
    total: int
    #: The reader is logged out, so reviews are left out (they are for logged-in students).
    reviews_hidden: bool = False


class RankedEntry(BaseModel):
    """One line of a ranking. `score` is the Bayesian average of the overall rating
    (docs/SPEC.md "Forum -> course attributes", prior weight k = 5, prior mean the period's
    average); only subjects with at least 3 reviews in the period are ranked."""

    rank: int
    #: A course code, a course list name (a Humanities sequence) or an instructor slug.
    id: str
    #: "CMSC 14100", "HUMA 11000-11100-11200" or the instructor's name.
    label: str
    #: The course title, the sequence's title or the instructor's department.
    detail: str | None = None
    score: float
    #: The plain average of the overall ratings, 1-5.
    mean: float
    n_reviews: int


class MajorRanking(BaseModel):
    program_id: str
    name: str
    #: The best-rated courses that count toward the major.
    items: list[RankedEntry] = []


class ForumStats(BaseModel):
    """Ratings of reviews posted in the period, for logged-in students only."""

    period: Period
    #: The first day counted: reviews posted on or after it.
    since: dt.date
    #: k in the Bayesian average.
    prior_weight: int
    #: Subjects with fewer reviews than this are not ranked.
    min_reviews: int
    #: m in the Bayesian average: the average overall rating of every review in the period.
    prior_mean: float | None = None
    n_reviews: int
    n_courses: int
    #: Share of the period's reviews that would recommend the course, 0-1.
    recommend_rate: float | None = None
    #: Average hours per week outside class over the period's reviews.
    workload_hours: float | None = None
    top_courses: list[RankedEntry] = []
    majors: list[MajorRanking] = []
    humanities: list[RankedEntry] = []
    instructors: list[RankedEntry] = []
