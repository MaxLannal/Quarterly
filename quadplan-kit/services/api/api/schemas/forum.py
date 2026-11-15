import datetime as dt
from typing import Literal, Self

from planner_core.models import TermId
from pydantic import BaseModel, Field, model_validator

from api.schemas.catalog import InstructorSummary, RatingSummary

Status = Literal["visible", "held", "removed"]
Vote = Literal[-1, 0, 1]


class ForumSummaryOut(BaseModel):
    text: str
    citations: list[int] = []
    n_posts: int
    computed_day: dt.date


class ForumPageOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    #: The other codes this course is cross-listed under; the page is the same under all.
    also_listed_as: list[str] = []
    instructor: InstructorSummary
    terms_taught: list[str] = []
    n_reviews: int = 0
    #: field -> counts for ratings 1..5 (overall, difficulty, intellectual_intensity)
    rating_distribution: dict[str, list[int]] = {}
    #: Averages over the visible reviews (workload, would-recommend share, the 1-5 scales).
    ratings: RatingSummary = RatingSummary()
    summary: ForumSummaryOut | None = None


class ForumPageSummary(BaseModel):
    page_id: int
    instructor: InstructorSummary
    terms_taught: list[str] = []
    ratings: RatingSummary = RatingSummary()


class CourseForumOut(BaseModel):
    """Course-level view: every instructor's page of one course, pooled (SPEC "Course-level
    view: the course page aggregates all its instructors")."""

    course_code: str
    course_title: str
    ratings: RatingSummary = RatingSummary()
    rating_distribution: dict[str, list[int]] = {}
    pages: list[ForumPageSummary] = []


GradeBucket = Literal["A-range", "B-range", "C or lower", "P/F", "prefer not to say"]


class ReviewRatingIn(BaseModel):
    overall: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    intellectual_intensity: int = Field(ge=1, le=5)
    workload_hours: float = Field(ge=0, le=100)
    would_recommend: bool
    grade_bucket: GradeBucket | None = None
    #: Optional: how fast the course moved, 1 (slow) to 5 (fast).
    pace: int | None = Field(default=None, ge=1, le=5)
    #: Optional: how strictly it was graded, 1 (generous) to 5 (strict).
    grading_strictness: int | None = Field(default=None, ge=1, le=5)


class PostCreate(BaseModel):
    """A review requires structured ratings and the term taken; a discussion post has neither."""

    kind: Literal["review", "discussion"]
    title: str | None = Field(default=None, max_length=200)
    body_md: str = Field(min_length=1, max_length=20000)
    term_taken: TermId | None = None
    ratings: ReviewRatingIn | None = None

    @model_validator(mode="after")
    def _review_fields(self) -> Self:
        if self.kind == "review" and (self.ratings is None or self.term_taken is None):
            raise ValueError("a review needs ratings and term_taken")
        if self.kind == "discussion" and self.ratings is not None:
            raise ValueError("a discussion post has no ratings")
        if not self.body_md.strip():
            raise ValueError("the post is empty")
        return self


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body_md: str | None = Field(default=None, min_length=1, max_length=20000)
    ratings: ReviewRatingIn | None = None
    term_taken: TermId | None = None


class PostOut(BaseModel):
    id: int
    page_id: int
    kind: Literal["review", "discussion"]
    pseudonym: str
    title: str | None = None
    body_md: str
    #: `body_md` rendered and sanitized on the server; the only HTML the client inserts.
    body_html: str = ""
    term_taken: str | None = None
    score: int
    my_vote: Vote = 0
    status: Status
    created_day: dt.date
    edited_day: dt.date | None = None
    ratings: ReviewRatingIn | None = None
    n_comments: int = 0
    #: True on the reader's own posts (they can edit, delete and ask for review).
    mine: bool = False
    #: Why the reader's own post is held or not published. Never set on others' posts.
    moderation_note: str | None = None


class CommentCreate(BaseModel):
    parent_id: int | None = None
    body_md: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def _not_blank(self) -> Self:
        if not self.body_md.strip():
            raise ValueError("the comment is empty")
        return self


class CommentOut(BaseModel):
    id: int
    post_id: int
    parent_id: int | None = None
    depth: int
    pseudonym: str
    body_md: str
    body_html: str = ""
    score: int
    my_vote: Vote = 0
    status: Status
    created_day: dt.date
    mine: bool = False
    moderation_note: str | None = None


class PostDetail(PostOut):
    #: Depth-first: each comment is followed by its replies, siblings in Best order.
    comments: list[CommentOut] = []


class VoteIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    #: 0 withdraws the vote.
    value: Vote


class VoteOut(BaseModel):
    score: int
    my_vote: Vote


class ForumReportIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    reason: str = Field(min_length=1, max_length=1000)


class ForumReportOut(BaseModel):
    id: int
    status: Literal["open", "upheld", "dismissed"]


# ------------------------------------------------------------------- Moderation queue (admin)


class ModerationReport(BaseModel):
    id: int
    reason: str
    created_day: dt.date
    #: True when the author reported their own post: a request for human review.
    from_author: bool = False


class ModerationItemOut(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    post_id: int
    page_id: int
    course_code: str
    instructor_name: str
    instructor_slug: str
    kind: Literal["review", "discussion", "comment"]
    pseudonym: str
    title: str | None = None
    body_md: str
    body_html: str
    status: Status
    created_day: dt.date
    #: The A4 label (or `classifier_unavailable`) that held or rejected it, if any.
    model_label: str | None = None
    reports: list[ModerationReport] = []


class ModerationDecision(BaseModel):
    #: approve: keep it published and dismiss the reports. remove: take it down and uphold them.
    decision: Literal["approve", "remove"]
    note: str | None = Field(default=None, max_length=1000)
    #: With "remove" only: also suspend the author from posting, commenting and voting for this
    #: many days. Suspensions are always an admin's choice, never automatic (P08-3).
    suspend_days: int | None = Field(default=None, ge=1, le=365)


class ModerationResult(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    status: Status
    author_suspended: bool = False
