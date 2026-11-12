import datetime as dt
from typing import Literal, Self

from planner_core.models import TermId
from pydantic import BaseModel, Field, model_validator

from api.schemas.catalog import InstructorSummary


class ForumSummaryOut(BaseModel):
    text: str
    citations: list[int] = []
    n_posts: int
    computed_day: dt.date


class ForumPageOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    instructor: InstructorSummary
    terms_taught: list[str] = []
    n_reviews: int = 0
    #: field -> counts for ratings 1..5 (overall, difficulty, intellectual_intensity)
    rating_distribution: dict[str, list[int]] = {}
    summary: ForumSummaryOut | None = None


class ReviewRatingIn(BaseModel):
    overall: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    intellectual_intensity: int = Field(ge=1, le=5)
    workload_hours: float = Field(ge=0, le=100)
    would_recommend: bool
    grade_bucket: Literal["A-range", "B-range", "C or lower", "P/F", "prefer not to say"] | None = (
        None
    )


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
        return self


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body_md: str | None = Field(default=None, min_length=1, max_length=20000)
    ratings: ReviewRatingIn | None = None


class PostOut(BaseModel):
    id: int
    page_id: int
    kind: Literal["review", "discussion"]
    pseudonym: str
    title: str | None = None
    body_md: str
    term_taken: str | None = None
    score: int
    my_vote: Literal[-1, 0, 1] = 0
    status: Literal["visible", "held", "removed"]
    created_day: dt.date
    ratings: ReviewRatingIn | None = None
    n_comments: int = 0


class CommentCreate(BaseModel):
    parent_id: int | None = None
    body_md: str = Field(min_length=1, max_length=10000)


class CommentOut(BaseModel):
    id: int
    post_id: int
    parent_id: int | None = None
    depth: int
    pseudonym: str
    body_md: str
    score: int
    my_vote: Literal[-1, 0, 1] = 0
    status: Literal["visible", "held", "removed"]
    created_day: dt.date


class PostDetail(PostOut):
    comments: list[CommentOut] = []


class VoteIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    #: 0 withdraws the vote.
    value: Literal[-1, 0, 1]


class VoteOut(BaseModel):
    score: int
    my_vote: Literal[-1, 0, 1]


class ForumReportIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int
    reason: str = Field(min_length=1, max_length=1000)


class ForumReportOut(BaseModel):
    id: int
    status: Literal["open", "upheld", "dismissed"]
