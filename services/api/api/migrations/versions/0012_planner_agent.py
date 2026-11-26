"""The planner agent (issues #17 and #18) and the interests question (issue #14)

Revision ID: 0012
Revises: 0011

- `student_profile.interests`: the General Information question that #14 asked for in all cases.
- `agent_run.state`: a paused planner run waiting for the student's answer.
- `change_set.run_id` and `change_set.meta`: the planner run and group of a proposal, so the
  proposals of one run can be accepted one by one (they re-base onto later edits).
- `profile_proposal`: answers from the planner chat that wait for the student's accept.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "student_profile",
        sa.Column("interests", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
    )
    op.add_column(
        "agent_run",
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("change_set", sa.Column("run_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_change_set_run_id_agent_run"),
        "change_set",
        "agent_run",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "change_set",
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "profile_proposal",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.String(length=48), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=24), server_default="planner_chat", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="proposed", nullable=False),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected')",
            name=op.f("ck_profile_proposal_status"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_profile_proposal_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_proposal")),
    )
    op.create_index(
        op.f("ix_profile_proposal_account_id"), "profile_proposal", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_proposal_account_id"), table_name="profile_proposal")
    op.drop_table("profile_proposal")
    op.drop_column("change_set", "meta")
    op.drop_constraint(op.f("fk_change_set_run_id_agent_run"), "change_set", type_="foreignkey")
    op.drop_column("change_set", "run_id")
    op.drop_column("agent_run", "state")
    op.drop_column("student_profile", "interests")
