"""SQLAlchemy 2 models for every table in SPEC "Data model" plus `course_list` and
`college_policy`. User-facing rows carry day-level dates only (`*_day`), never timestamps.
Decision 5: `account.email` is the only place a user's email is stored."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base
from api.db.types import Ltree

TODAY = sa.text("CURRENT_DATE")


def _id() -> Mapped[int]:
    return mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _texts() -> Mapped[list[str]]:
    return mapped_column(ARRAY(sa.Text), nullable=False, server_default="{}")


# ---------------------------------------------------------------------------------- Catalog


class CatalogYear(Base):
    __tablename__ = "catalog_year"
    id: Mapped[str] = mapped_column(sa.String(7), primary_key=True)  # "2026-27"
    published_at: Mapped[dt.date | None]


class Course(Base):
    __tablename__ = "course"
    __table_args__ = (
        sa.UniqueConstraint("catalog_year", "code"),
        sa.Index("ix_course_code", "code"),
        sa.Index(
            "ix_course_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )
    id: Mapped[int] = _id()
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"))
    subject: Mapped[str] = mapped_column(sa.String(8))
    number: Mapped[str] = mapped_column(sa.String(8))
    code: Mapped[str] = mapped_column(sa.String(16))  # subject + " " + number
    title: Mapped[str] = mapped_column(sa.Text)
    units: Mapped[int] = mapped_column(server_default="100")
    description: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[str | None] = mapped_column(sa.Text)
    core_tags: Mapped[list[str]] = _texts()
    tags: Mapped[list[str]] = _texts()
    repeatable: Mapped[bool] = mapped_column(server_default=sa.false())
    source_id: Mapped[int | None] = mapped_column(sa.ForeignKey("source_snapshot.id"))
    source: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # {url|snapshot_id, quote}
    needs_review: Mapped[bool] = mapped_column(server_default=sa.false())


class CrosslistGroup(Base):
    __tablename__ = "crosslist_group"
    group_id: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        sa.ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )


class CourseRelation(Base):
    __tablename__ = "course_relation"
    __table_args__ = (
        sa.UniqueConstraint("course_a", "course_b", "kind"),
        sa.CheckConstraint("kind IN ('equivalent', 'mutually_exclusive', 'replaces')", name="kind"),
    )
    id: Mapped[int] = _id()
    course_a: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    course_b: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(sa.String(24))
    source: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Requisite(Base):
    __tablename__ = "requisite"
    __table_args__ = (sa.UniqueConstraint("course_id", "catalog_year"),)
    id: Mapped[int] = _id()
    course_id: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"))
    prereq: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # planner_core Expr
    coreq: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    restrictions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raw_text: Mapped[str | None] = mapped_column(sa.Text)
    source: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    needs_review: Mapped[bool] = mapped_column(server_default=sa.false())


class CourseList(Base):
    __tablename__ = "course_list"
    __table_args__ = (sa.UniqueConstraint("catalog_year", "name"),)
    id: Mapped[int] = _id()
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"))
    name: Mapped[str] = mapped_column(sa.String(128))
    label: Mapped[str | None] = mapped_column(sa.Text)
    course_ids: Mapped[list[int]] = mapped_column(
        ARRAY(sa.BigInteger), nullable=False, server_default="{}"
    )
    sublists: Mapped[list[str]] = _texts()  # names of member lists (one per sequence)
    source_id: Mapped[int | None] = mapped_column(sa.ForeignKey("source_snapshot.id"))
    source: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    needs_review: Mapped[bool] = mapped_column(server_default=sa.false())


# --------------------------------------------------------------------------------- Schedule


class Term(Base):
    __tablename__ = "term"
    __table_args__ = (sa.CheckConstraint("quarter IN ('AU', 'WI', 'SP', 'SU')", name="quarter"),)
    id: Mapped[str] = mapped_column(sa.String(7), primary_key=True)  # "2026-AU"
    year: Mapped[int]
    quarter: Mapped[str] = mapped_column(sa.String(2))
    start: Mapped[dt.date | None]
    end: Mapped[dt.date | None]


class Instructor(Base):
    __tablename__ = "instructor"
    id: Mapped[int] = _id()
    slug: Mapped[str] = mapped_column(sa.String(128), unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text)
    department: Mapped[str | None] = mapped_column(sa.Text)
    aliases: Mapped[list[str]] = _texts()


class Section(Base):
    __tablename__ = "section"
    __table_args__ = (sa.Index("ix_section_term_course", "term_id", "course_id"),)
    id: Mapped[int] = _id()
    term_id: Mapped[str] = mapped_column(sa.ForeignKey("term.id"))
    course_id: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    section_no: Mapped[str] = mapped_column(sa.String(16))
    component: Mapped[str | None] = mapped_column(sa.String(32))
    instructor_ids: Mapped[list[int]] = mapped_column(
        ARRAY(sa.BigInteger), nullable=False, server_default="{}"
    )
    meetings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    capacity: Mapped[int | None]
    status: Mapped[str | None] = mapped_column(sa.String(32))
    source_id: Mapped[int | None] = mapped_column(sa.ForeignKey("source_snapshot.id"))
    scraped_at: Mapped[dt.datetime | None] = mapped_column(sa.DateTime(timezone=True))


class CourseInstructor(Base):
    """One forum page per row."""

    __tablename__ = "course_instructor"
    __table_args__ = (
        sa.UniqueConstraint("course_id", "instructor_id"),
        sa.Index("ix_course_instructor_instructor", "instructor_id"),
    )
    id: Mapped[int] = _id()
    course_id: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    instructor_id: Mapped[int] = mapped_column(sa.ForeignKey("instructor.id", ondelete="CASCADE"))
    first_term: Mapped[str | None] = mapped_column(sa.ForeignKey("term.id"))
    last_term: Mapped[str | None] = mapped_column(sa.ForeignKey("term.id"))
    n_terms: Mapped[int] = mapped_column(server_default="0")


class OfferingPattern(Base):
    __tablename__ = "offering_pattern"
    __table_args__ = (sa.UniqueConstraint("course_id", "quarter"),)
    id: Mapped[int] = _id()
    course_id: Mapped[int] = mapped_column(sa.ForeignKey("course.id", ondelete="CASCADE"))
    quarter: Mapped[str] = mapped_column(sa.String(2))
    p_offered: Mapped[float]
    evidence_terms: Mapped[list[str]] = _texts()
    method: Mapped[str] = mapped_column(sa.String(32))


# --------------------------------------------------------------------------------- Programs


class Program(Base):
    __tablename__ = "program"
    id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)  # slug, e.g. cmsc-bs
    name: Mapped[str] = mapped_column(sa.Text)
    type: Mapped[str] = mapped_column(sa.String(32))
    degree: Mapped[str | None] = mapped_column(sa.String(8))
    department: Mapped[str | None] = mapped_column(sa.Text)
    parent_id: Mapped[str | None] = mapped_column(sa.ForeignKey("program.id"))


class ProgramVersion(Base):
    __tablename__ = "program_version"
    __table_args__ = (
        sa.UniqueConstraint("program_id", "catalog_year"),
        sa.CheckConstraint("status IN ('draft', 'review', 'published')", name="status"),
    )
    id: Mapped[int] = _id()
    program_id: Mapped[str] = mapped_column(sa.ForeignKey("program.id"))
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"))
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)  # planner_core ProgramRules
    status: Mapped[str] = mapped_column(sa.String(16), server_default="draft")
    verified_by: Mapped[str | None] = mapped_column(sa.Text)
    verified_at: Mapped[dt.date | None]
    source_ids: Mapped[list[int]] = mapped_column(
        ARRAY(sa.BigInteger), nullable=False, server_default="{}"
    )
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    checksum: Mapped[str] = mapped_column(sa.String(80))


class ProgramRelation(Base):
    __tablename__ = "program_relation"
    __table_args__ = (
        sa.CheckConstraint("kind IN ('requires', 'excludes', 'share_limit')", name="kind"),
    )
    id: Mapped[int] = _id()
    program_a: Mapped[str] = mapped_column(sa.ForeignKey("program.id"))
    program_b: Mapped[str] = mapped_column(sa.ForeignKey("program.id"))
    kind: Mapped[str] = mapped_column(sa.String(16))
    n: Mapped[int | None]


class CollegePolicy(Base):
    """College-wide rules per catalog year (planner_core CollegePolicy)."""

    __tablename__ = "college_policy"
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"), primary_key=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(16), server_default="draft")
    checksum: Mapped[str] = mapped_column(sa.String(80))


# ------------------------------------------------------------------------------- Attributes


class AttributeDef(Base):
    __tablename__ = "attribute_def"
    key: Mapped[str] = mapped_column(sa.String(32), primary_key=True)
    scale: Mapped[str] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text)


class AttributeValue(Base):
    __tablename__ = "attribute_value"
    __table_args__ = (sa.UniqueConstraint("subject_type", "subject_id", "key"),)
    id: Mapped[int] = _id()
    subject_type: Mapped[str] = mapped_column(sa.String(24))  # course | course_instructor
    subject_id: Mapped[str] = mapped_column(sa.String(64))
    key: Mapped[str] = mapped_column(sa.ForeignKey("attribute_def.key"))
    value: Mapped[float]
    ci_low: Mapped[float | None]
    ci_high: Mapped[float | None]
    n: Mapped[int] = mapped_column(server_default="0")
    method: Mapped[str] = mapped_column(sa.String(16))  # prior | forum | blend | estimate
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    computed_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


# --------------------------------------------------------------------- Provenance and review


class SourceSnapshot(Base):
    __tablename__ = "source_snapshot"
    id: Mapped[int] = _id()
    url: Mapped[str] = mapped_column(sa.Text)
    fetched_at: Mapped[dt.datetime] = mapped_column(sa.DateTime(timezone=True))
    sha256: Mapped[str] = mapped_column(sa.String(64), index=True)
    storage_key: Mapped[str] = mapped_column(sa.Text)
    content_type: Mapped[str | None] = mapped_column(sa.String(128))


class ExtractionRun(Base):
    __tablename__ = "extraction_run"
    id: Mapped[int] = _id()
    kind: Mapped[str] = mapped_column(sa.String(32))
    model: Mapped[str] = mapped_column(sa.String(64))
    prompt_version: Mapped[str] = mapped_column(sa.String(32))
    input_snapshot_ids: Mapped[list[int]] = mapped_column(
        ARRAY(sa.BigInteger), nullable=False, server_default="{}"
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(16))
    cost_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 4))


class ReviewItem(Base):
    __tablename__ = "review_item"
    id: Mapped[int] = _id()
    target_type: Mapped[str] = mapped_column(sa.String(32))
    target_id: Mapped[str] = mapped_column(sa.String(64))
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), server_default="open")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("account.id", ondelete="SET NULL")
    )
    decided_at: Mapped[dt.date | None]  # day-level: decided_by is a user


# ----------------------------------------------------------------------- Plans and goals


class Plan(Base):
    __tablename__ = "plan"
    id: Mapped[uuid.UUID] = _uuid()
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("account.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(sa.Text)
    catalog_year: Mapped[str] = mapped_column(sa.ForeignKey("catalog_year.id"))
    entry_term: Mapped[str] = mapped_column(sa.String(7))
    entry_year_level: Mapped[int] = mapped_column(server_default="1")
    #: Last quarter (planner_core PlanState.graduation_term); NULL = the default.
    graduation_term: Mapped[str | None] = mapped_column(sa.String(7))
    placements: Mapped[list[str]] = _texts()
    overload_reasons: Mapped[dict[str, str]] = mapped_column(JSONB, server_default="{}")
    is_primary: Mapped[bool] = mapped_column(server_default=sa.false())
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
    updated_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class PlanProgram(Base):
    __tablename__ = "plan_program"
    __table_args__ = (sa.UniqueConstraint("plan_id", "program_version_id"),)
    id: Mapped[int] = _id()
    plan_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("plan.id", ondelete="CASCADE"))
    program_version_id: Mapped[int] = mapped_column(sa.ForeignKey("program_version.id"))
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class PlanItem(Base):
    __tablename__ = "plan_item"
    __table_args__ = (
        sa.CheckConstraint("(course_id IS NULL) <> (slot_ref IS NULL)", name="course_or_slot"),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'transfer', 'exam')", name="status"
        ),
        sa.Index("ix_plan_item_plan_term", "plan_id", "term_id"),
    )
    id: Mapped[int] = _id()
    plan_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("plan.id", ondelete="CASCADE"))
    course_id: Mapped[int | None] = mapped_column(sa.ForeignKey("course.id"))
    slot_ref: Mapped[str | None] = mapped_column(sa.Text)
    term_id: Mapped[str] = mapped_column(sa.String(7))
    status: Mapped[str] = mapped_column(sa.String(16), server_default="planned")
    locked: Mapped[bool] = mapped_column(server_default=sa.false())
    units: Mapped[int | None]
    grading: Mapped[str] = mapped_column(sa.String(16), server_default="letter")
    grade: Mapped[str | None] = mapped_column(sa.String(4))


class Credit(Base):
    __tablename__ = "credit"
    id: Mapped[int] = _id()
    plan_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("plan.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(sa.String(16))  # AP | placement | transfer
    label: Mapped[str] = mapped_column(sa.Text)
    maps_to_course_id: Mapped[int | None] = mapped_column(sa.ForeignKey("course.id"))
    units: Mapped[int] = mapped_column(server_default="0")


class Goal(Base):
    __tablename__ = "goal"
    __table_args__ = (sa.UniqueConstraint("plan_id", "goal_key"),)
    id: Mapped[int] = _id()
    plan_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("plan.id", ondelete="CASCADE"))
    goal_key: Mapped[str] = mapped_column(sa.String(64))  # planner_core Goal.id
    scope: Mapped[str] = mapped_column(sa.String(8))
    term_id: Mapped[str | None] = mapped_column(sa.String(7))
    type: Mapped[str] = mapped_column(sa.String(32))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    hard: Mapped[bool] = mapped_column(server_default=sa.false())
    weight: Mapped[float] = mapped_column(server_default="1")


class VerificationReport(Base):
    __tablename__ = "verification_report"
    __table_args__ = (sa.UniqueConstraint("plan_hash", "core_version"),)
    id: Mapped[int] = _id()
    plan_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("plan.id", ondelete="CASCADE"))
    plan_hash: Mapped[str] = mapped_column(sa.String(80), index=True)
    core_version: Mapped[str] = mapped_column(sa.String(32))
    status: Mapped[str] = mapped_column(sa.String(16))
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    certificate: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class ChangeSet(Base):
    __tablename__ = "change_set"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('proposed', 'applied', 'discarded', 'stale')", name="status"
        ),
        sa.CheckConstraint("origin IN ('generate', 'chat', 'user')", name="origin"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    plan_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("plan.id", ondelete="CASCADE"), index=True
    )
    origin: Mapped[str] = mapped_column(sa.String(16))
    ops: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    base_plan_hash: Mapped[str] = mapped_column(sa.String(80))
    preview_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(sa.String(16), server_default="proposed")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


# ----------------------------------------------------------------------- Agents and LLM usage


class AgentRun(Base):
    __tablename__ = "agent_run"
    id: Mapped[uuid.UUID] = _uuid()
    kind: Mapped[str] = mapped_column(sa.String(32))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("plan.id", ondelete="SET NULL"))
    model: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(16))
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    tokens: Mapped[int] = mapped_column(server_default="0")
    cost_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 4))
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class ChatMessage(Base):
    """Deleted after 30 days (created_day)."""

    __tablename__ = "chat_message"
    id: Mapped[int] = _id()
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("agent_run.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(sa.String(16))
    content: Mapped[str] = mapped_column(sa.Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class LlmCall(Base):
    """No user identifier, by rule."""

    __tablename__ = "llm_call"
    id: Mapped[int] = _id()
    task: Mapped[str] = mapped_column(sa.String(48))
    model: Mapped[str] = mapped_column(sa.String(64))
    prompt_version: Mapped[str] = mapped_column(sa.String(32))
    in_tokens: Mapped[int]
    out_tokens: Mapped[int]
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 6))
    latency_ms: Mapped[int]
    ok: Mapped[bool]
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


# ------------------------------------------------------------------------------------ Forum


class Pseudonym(Base):
    __tablename__ = "pseudonym"
    __table_args__ = (
        sa.UniqueConstraint("author_ref", "course_instructor_id"),
        sa.UniqueConstraint("course_instructor_id", "handle"),
    )
    id: Mapped[int] = _id()
    author_ref: Mapped[str] = mapped_column(
        sa.String(64)
    )  # HMAC(server_key, account_id || page_id)
    course_instructor_id: Mapped[int] = mapped_column(
        sa.ForeignKey("course_instructor.id", ondelete="CASCADE")
    )
    handle: Mapped[str] = mapped_column(sa.String(64))


class Post(Base):
    __tablename__ = "post"
    __table_args__ = (
        sa.CheckConstraint("kind IN ('review', 'discussion')", name="kind"),
        sa.CheckConstraint("status IN ('visible', 'held', 'removed')", name="status"),
        sa.Index("ix_post_page", "course_instructor_id", "status"),
        # One review per account per page.
        sa.Index(
            "uq_post_one_review_per_author",
            "course_instructor_id",
            "author_ref",
            unique=True,
            postgresql_where=sa.text("kind = 'review'"),
        ),
    )
    id: Mapped[int] = _id()
    course_instructor_id: Mapped[int] = mapped_column(
        sa.ForeignKey("course_instructor.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(sa.String(16))
    author_ref: Mapped[str | None] = mapped_column(sa.String(64))  # NULL = "[deleted account]"
    pseudonym_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("pseudonym.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(sa.Text)
    body_md: Mapped[str] = mapped_column(sa.Text)
    term_taken: Mapped[str | None] = mapped_column(sa.String(7))
    score: Mapped[int] = mapped_column(server_default="0")
    status: Mapped[str] = mapped_column(sa.String(16), server_default="visible")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
    edited_day: Mapped[dt.date | None]


class ReviewRating(Base):
    __tablename__ = "review_rating"
    __table_args__ = (
        sa.CheckConstraint("overall BETWEEN 1 AND 5", name="overall"),
        sa.CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty"),
        sa.CheckConstraint("intellectual_intensity BETWEEN 1 AND 5", name="intensity"),
        sa.CheckConstraint("workload_hours >= 0", name="workload"),
        sa.CheckConstraint("pace BETWEEN 1 AND 5", name="pace"),
        sa.CheckConstraint("grading_strictness BETWEEN 1 AND 5", name="grading"),
    )
    post_id: Mapped[int] = mapped_column(
        sa.ForeignKey("post.id", ondelete="CASCADE"), primary_key=True
    )
    overall: Mapped[int] = mapped_column(sa.SmallInteger)
    difficulty: Mapped[int] = mapped_column(sa.SmallInteger)
    intellectual_intensity: Mapped[int] = mapped_column(sa.SmallInteger)
    workload_hours: Mapped[float]
    would_recommend: Mapped[bool]
    grade_bucket: Mapped[str | None] = mapped_column(sa.String(16))
    #: Optional (Q11, Richard 2026-11-14): how fast the course moved, how strictly it was graded.
    pace: Mapped[int | None] = mapped_column(sa.SmallInteger)
    grading_strictness: Mapped[int | None] = mapped_column(sa.SmallInteger)


class Comment(Base):
    __tablename__ = "comment"
    __table_args__ = (sa.Index("ix_comment_path", "path", postgresql_using="gist"),)
    id: Mapped[int] = _id()
    post_id: Mapped[int] = mapped_column(sa.ForeignKey("post.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(sa.ForeignKey("comment.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Ltree)
    author_ref: Mapped[str | None] = mapped_column(sa.String(64))
    pseudonym_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("pseudonym.id", ondelete="SET NULL")
    )
    body_md: Mapped[str] = mapped_column(sa.Text)
    score: Mapped[int] = mapped_column(server_default="0")
    status: Mapped[str] = mapped_column(sa.String(16), server_default="visible")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class Vote(Base):
    __tablename__ = "vote"
    __table_args__ = (
        sa.UniqueConstraint("voter_ref", "target_type", "target_id"),
        sa.CheckConstraint("value IN (-1, 1)", name="value"),
    )
    id: Mapped[int] = _id()
    voter_ref: Mapped[str] = mapped_column(sa.String(64))  # HMAC(server_key, account_id || page_id)
    target_type: Mapped[str] = mapped_column(sa.String(16))
    target_id: Mapped[int] = mapped_column(sa.BigInteger)
    value: Mapped[int] = mapped_column(sa.SmallInteger)


class Report(Base):
    __tablename__ = "report"
    id: Mapped[int] = _id()
    target_type: Mapped[str] = mapped_column(sa.String(16))
    target_id: Mapped[int] = mapped_column(sa.BigInteger)
    reason: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), server_default="open")
    reporter_ref: Mapped[str | None] = mapped_column(sa.String(64))
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class ModerationAction(Base):
    __tablename__ = "moderation_action"
    id: Mapped[int] = _id()
    target_type: Mapped[str] = mapped_column(sa.String(16))
    target_id: Mapped[int] = mapped_column(sa.BigInteger)
    action: Mapped[str] = mapped_column(sa.String(32))
    reason: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), server_default="done")
    actor: Mapped[str] = mapped_column(sa.String(16))  # model | admin
    actor_account_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("account.id", ondelete="SET NULL")
    )
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class ForumSummary(Base):
    __tablename__ = "forum_summary"
    course_instructor_id: Mapped[int] = mapped_column(
        sa.ForeignKey("course_instructor.id", ondelete="CASCADE"), primary_key=True
    )
    text: Mapped[str] = mapped_column(sa.Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    model: Mapped[str] = mapped_column(sa.String(64))
    n_posts: Mapped[int]
    computed_at: Mapped[dt.date]


# --------------------------------------------------------------------------------- Accounts


class Account(Base):
    """Decision 5: the verified email is stored here and nowhere else; never logged."""

    __tablename__ = "account"
    __table_args__ = (
        sa.CheckConstraint("role IN ('user', 'curator', 'admin')", name="role"),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
        sa.Index("uq_account_username_lower", sa.text("lower(username)"), unique=True),
    )
    id: Mapped[uuid.UUID] = _uuid()
    username: Mapped[str] = mapped_column(sa.String(32))
    email: Mapped[str] = mapped_column(sa.String(254), unique=True)
    email_verified_day: Mapped[dt.date]
    password_hash: Mapped[str | None] = mapped_column(sa.Text)  # argon2id
    passkey_credential: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    role: Mapped[str] = mapped_column(sa.String(16), server_default="user")
    status: Mapped[str] = mapped_column(sa.String(16), server_default="active")
    suspended_until: Mapped[dt.date | None]
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


# ------------------------------------------------- Campus companion (docs/BEST-OF-UCHICAGO-PLAN.md)


class StudentProfile(Base):
    """The dashboard's portrait of one student (`/me`). Keyed by the account like a plan: it is
    the student's own data, exported with the account and deleted with it (cascade). The email is
    never copied here (decision 5): the dashboard reads it from `account`."""

    __tablename__ = "student_profile"
    __table_args__ = (
        sa.CheckConstraint(
            "class_year IS NULL OR class_year BETWEEN 2020 AND 2040", name="class_year_range"
        ),
        sa.CheckConstraint(
            "humanities_goal IS NULL OR humanities_goal IN ('pass', 'balance', 'enjoy', 'deep')",
            name="humanities_goal",
        ),
        sa.CheckConstraint(
            "workload IS NULL OR workload IN ('light', 'balanced', 'intense')", name="workload"
        ),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("account.id", ondelete="CASCADE"), primary_key=True
    )
    class_year: Mapped[int | None] = mapped_column(sa.SmallInteger)
    #: Program ids (program.id) the student is considering.
    intended_programs: Mapped[list[str]] = _texts()
    interests: Mapped[list[str]] = _texts()
    research_areas: Mapped[list[str]] = _texts()
    #: pass ("just get through the Core") | balance | enjoy (specific topics) | deep.
    humanities_goal: Mapped[str | None] = mapped_column(sa.String(16))
    humanities_topics: Mapped[list[str]] = _texts()
    humanities_note: Mapped[str | None] = mapped_column(sa.Text)
    career_plans: Mapped[str | None] = mapped_column(sa.Text)
    career_paths: Mapped[list[str]] = _texts()
    future_domains: Mapped[list[str]] = _texts()
    constraints: Mapped[list[str]] = _texts()
    workload: Mapped[str | None] = mapped_column(sa.String(16))
    #: Feed category keys the student focuses on (api.feed categories).
    feed_categories: Mapped[list[str]] = _texts()
    #: {headline, summary, themes: [str]}: written by the interviewer, kept by the student.
    portrait: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    #: The interviewer's memory: {covered: [topic], turns: [{role, text}] (last 24, scrubbed)}.
    interview: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    #: {threads: [commons_thread.id], courses: [course code]}.
    follows: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    #: High-water marks of what the student has seen (/me/updates): {thread, reply, post, comment}.
    updates_seen: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
    updated_day: Mapped[dt.date] = mapped_column(server_default=TODAY)


class CommonsThread(Base):
    """A question in the Commons (`/forum`), optionally about one course. Authors are stored as
    `commons_ref(account_id, thread_id)` (api.commons), so posts on different threads cannot be
    linked. `bot_state`: pending (no bot answer yet) | answered | failed | off."""

    __tablename__ = "commons_thread"
    __table_args__ = (
        sa.CheckConstraint("status IN ('visible', 'removed', 'deleted')", name="status"),
        sa.CheckConstraint(
            "bot_state IN ('pending', 'answered', 'failed', 'off')", name="bot_state"
        ),
    )
    id: Mapped[int] = _id()
    course_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("course.id", ondelete="SET NULL"), index=True
    )
    #: NULL once the author deleted their account ("[deleted account]").
    author_ref: Mapped[str | None] = mapped_column(sa.String(64))
    title: Mapped[str] = mapped_column(sa.Text)
    body_md: Mapped[str] = mapped_column(sa.Text, server_default="")
    tags: Mapped[list[str]] = _texts()
    score: Mapped[int] = mapped_column(server_default="0")
    reply_count: Mapped[int] = mapped_column(server_default="0")
    accepted_reply_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    #: The newest reply's id, for "active" ordering and the live new-reply banner.
    last_reply_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    bot_state: Mapped[str] = mapped_column(sa.String(16), server_default="pending")
    status: Mapped[str] = mapped_column(sa.String(16), server_default="visible")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
    edited_day: Mapped[dt.date | None]


class CommonsReply(Base):
    """An answer (depth 0) or a nested comment (`parent_id`) on a Commons thread. `kind` bot is
    the AI's answer: written by an agent, stored by the harness, always labelled as AI."""

    __tablename__ = "commons_reply"
    __table_args__ = (
        sa.CheckConstraint("kind IN ('human', 'bot')", name="kind"),
        sa.CheckConstraint("status IN ('visible', 'removed', 'deleted')", name="status"),
    )
    id: Mapped[int] = _id()
    thread_id: Mapped[int] = mapped_column(
        sa.ForeignKey("commons_thread.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("commons_reply.id", ondelete="CASCADE")
    )
    depth: Mapped[int] = mapped_column(sa.SmallInteger, server_default="0")
    author_ref: Mapped[str | None] = mapped_column(sa.String(64))
    kind: Mapped[str] = mapped_column(sa.String(8), server_default="human")
    body_md: Mapped[str] = mapped_column(sa.Text)
    #: The bot's citations: [{kind, id, label}] (checked like the advisor's).
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    score: Mapped[int] = mapped_column(server_default="0")
    status: Mapped[str] = mapped_column(sa.String(16), server_default="visible")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
    edited_day: Mapped[dt.date | None]


class CommonsPseudonym(Base):
    """Per-thread random handle of an author (like `pseudonym` for forum pages)."""

    __tablename__ = "commons_pseudonym"
    __table_args__ = (
        sa.UniqueConstraint("thread_id", "author_ref", name="uq_commons_pseudonym_author"),
        sa.UniqueConstraint("thread_id", "handle", name="uq_commons_pseudonym_handle"),
    )
    id: Mapped[int] = _id()
    thread_id: Mapped[int] = mapped_column(sa.ForeignKey("commons_thread.id", ondelete="CASCADE"))
    author_ref: Mapped[str] = mapped_column(sa.String(64))
    handle: Mapped[str] = mapped_column(sa.String(64))


class CommonsVote(Base):
    __tablename__ = "commons_vote"
    __table_args__ = (
        sa.CheckConstraint("target_type IN ('thread', 'reply')", name="target_type"),
        sa.CheckConstraint("value IN (-1, 1)", name="value"),
        sa.UniqueConstraint("target_type", "target_id", "voter_ref", name="uq_commons_vote"),
    )
    id: Mapped[int] = _id()
    target_type: Mapped[str] = mapped_column(sa.String(8))
    target_id: Mapped[int] = mapped_column(sa.BigInteger)
    voter_ref: Mapped[str] = mapped_column(sa.String(64))
    value: Mapped[int] = mapped_column(sa.SmallInteger)


class CommonsReport(Base):
    __tablename__ = "commons_report"
    __table_args__ = (
        sa.CheckConstraint("target_type IN ('thread', 'reply')", name="target_type"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="status"),
    )
    id: Mapped[int] = _id()
    target_type: Mapped[str] = mapped_column(sa.String(8))
    target_id: Mapped[int] = mapped_column(sa.BigInteger)
    reason: Mapped[str] = mapped_column(sa.Text)
    reporter_ref: Mapped[str | None] = mapped_column(sa.String(64))
    status: Mapped[str] = mapped_column(sa.String(16), server_default="open")
    created_day: Mapped[dt.date] = mapped_column(server_default=TODAY)
