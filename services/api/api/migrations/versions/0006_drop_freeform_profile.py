"""Drop the freeform dashboard fields and the portrait (Issue #16, Issue #14 D2)

Revision ID: 0006
Revises: 0005

The General Information questions replace the old freeform interview (interests, humanities,
career, future fields, constraints, workload) and the portrait (Issue #16 D4). No code reads
these columns now. Downgrade adds them back empty.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXTS = ("interests", "humanities_topics", "career_paths", "future_domains", "constraints")


def upgrade() -> None:
    op.drop_constraint(op.f("ck_student_profile_humanities_goal"), "student_profile", type_="check")
    op.drop_constraint(op.f("ck_student_profile_workload"), "student_profile", type_="check")
    for name in (
        *_TEXTS,
        "humanities_goal",
        "humanities_note",
        "career_plans",
        "workload",
        "portrait",
    ):
        op.drop_column("student_profile", name)


def downgrade() -> None:
    for name in _TEXTS:
        op.add_column(
            "student_profile",
            sa.Column(name, postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        )
    op.add_column("student_profile", sa.Column("humanities_goal", sa.String(16), nullable=True))
    op.add_column("student_profile", sa.Column("humanities_note", sa.Text(), nullable=True))
    op.add_column("student_profile", sa.Column("career_plans", sa.Text(), nullable=True))
    op.add_column("student_profile", sa.Column("workload", sa.String(16), nullable=True))
    op.add_column(
        "student_profile",
        sa.Column(
            "portrait",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_student_profile_humanities_goal"),
        "student_profile",
        "humanities_goal IS NULL OR humanities_goal IN ('pass', 'balance', 'enjoy', 'deep')",
    )
    op.create_check_constraint(
        op.f("ck_student_profile_workload"),
        "student_profile",
        "workload IS NULL OR workload IN ('light', 'balanced', 'intense')",
    )
