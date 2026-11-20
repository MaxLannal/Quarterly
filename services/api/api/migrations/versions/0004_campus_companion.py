"""Campus companion: student_profile, pathway and the Commons (docs/BEST-OF-UCHICAGO-PLAN.md)

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commons_report",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("target_type", sa.String(length=8), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reporter_ref", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.CheckConstraint("status IN ('open', 'closed')", name=op.f("ck_commons_report_status")),
        sa.CheckConstraint(
            "target_type IN ('thread', 'reply')", name=op.f("ck_commons_report_target_type")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commons_report")),
    )
    op.create_table(
        "commons_vote",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("target_type", sa.String(length=8), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("voter_ref", sa.String(length=64), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "target_type IN ('thread', 'reply')", name=op.f("ck_commons_vote_target_type")
        ),
        sa.CheckConstraint("value IN (-1, 1)", name=op.f("ck_commons_vote_value")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commons_vote")),
        sa.UniqueConstraint("target_type", "target_id", "voter_ref", name="uq_commons_vote"),
    )
    op.create_table(
        "pathway",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="major", nullable=False),
        sa.Column("program_ids", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "courses", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "milestones",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "fit", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("origin", sa.String(length=8), server_default="ai", nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("updated_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'user')", name=op.f("ck_pathway_origin")),
        sa.CheckConstraint(
            "status IN ('open', 'chosen', 'archived')", name=op.f("ck_pathway_status")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_pathway_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pathway")),
    )
    op.create_index(op.f("ix_pathway_account_id"), "pathway", ["account_id"], unique=False)
    op.create_index(
        "uq_pathway_one_chosen",
        "pathway",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'chosen'"),
    )
    op.create_table(
        "student_profile",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("class_year", sa.SmallInteger(), nullable=True),
        sa.Column(
            "intended_programs", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("interests", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "research_areas", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("humanities_goal", sa.String(length=16), nullable=True),
        sa.Column(
            "humanities_topics", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("humanities_note", sa.Text(), nullable=True),
        sa.Column("career_plans", sa.Text(), nullable=True),
        sa.Column("career_paths", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "future_domains", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("constraints", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("workload", sa.String(length=16), nullable=True),
        sa.Column(
            "feed_categories", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "portrait", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "interview",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "follows", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "updates_seen",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("updated_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.CheckConstraint(
            "humanities_goal IS NULL OR humanities_goal IN ('pass', 'balance', 'enjoy', 'deep')",
            name=op.f("ck_student_profile_humanities_goal"),
        ),
        sa.CheckConstraint(
            "workload IS NULL OR workload IN ('light', 'balanced', 'intense')",
            name=op.f("ck_student_profile_workload"),
        ),
        sa.CheckConstraint(
            "class_year IS NULL OR class_year BETWEEN 2020 AND 2040",
            name=op.f("ck_student_profile_class_year_range"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_student_profile_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_student_profile")),
    )
    op.create_table(
        "commons_thread",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("author_ref", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body_md", sa.Text(), server_default="", nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reply_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accepted_reply_id", sa.BigInteger(), nullable=True),
        sa.Column("last_reply_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_state", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="visible", nullable=False),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("edited_day", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "bot_state IN ('pending', 'answered', 'failed', 'off')",
            name=op.f("ck_commons_thread_bot_state"),
        ),
        sa.CheckConstraint(
            "status IN ('visible', 'removed', 'deleted')", name=op.f("ck_commons_thread_status")
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["course.id"],
            name=op.f("fk_commons_thread_course_id_course"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commons_thread")),
    )
    op.create_index(
        op.f("ix_commons_thread_course_id"), "commons_thread", ["course_id"], unique=False
    )
    op.create_table(
        "commons_pseudonym",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column("author_ref", sa.String(length=64), nullable=False),
        sa.Column("handle", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["commons_thread.id"],
            name=op.f("fk_commons_pseudonym_thread_id_commons_thread"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commons_pseudonym")),
        sa.UniqueConstraint("thread_id", "author_ref", name="uq_commons_pseudonym_author"),
        sa.UniqueConstraint("thread_id", "handle", name="uq_commons_pseudonym_handle"),
    )
    op.create_table(
        "commons_reply",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("depth", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("author_ref", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=8), server_default="human", nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="visible", nullable=False),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("edited_day", sa.Date(), nullable=True),
        sa.CheckConstraint("kind IN ('human', 'bot')", name=op.f("ck_commons_reply_kind")),
        sa.CheckConstraint(
            "status IN ('visible', 'removed', 'deleted')", name=op.f("ck_commons_reply_status")
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["commons_reply.id"],
            name=op.f("fk_commons_reply_parent_id_commons_reply"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["commons_thread.id"],
            name=op.f("fk_commons_reply_thread_id_commons_thread"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commons_reply")),
    )
    op.create_index(
        op.f("ix_commons_reply_thread_id"), "commons_reply", ["thread_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_commons_reply_thread_id"), table_name="commons_reply")
    op.drop_table("commons_reply")
    op.drop_table("commons_pseudonym")
    op.drop_index(op.f("ix_commons_thread_course_id"), table_name="commons_thread")
    op.drop_table("commons_thread")
    op.drop_table("student_profile")
    op.drop_index(
        "uq_pathway_one_chosen", table_name="pathway", postgresql_where=sa.text("status = 'chosen'")
    )
    op.drop_index(op.f("ix_pathway_account_id"), table_name="pathway")
    op.drop_table("pathway")
    op.drop_table("commons_vote")
    op.drop_table("commons_report")
