"""Keep the planner lock of a taken course in the student record (Blocker 2, review of PR #21)

Revision ID: 0007
Revises: 0006

0005 moved each primary plan's completed and in-progress courses into `student_course` with
their grading and units, but not their lock. This adds `student_course.locked` and copies the
lock from the primary plan's old copies, which stay in `plan_item` until that plan is saved
again. Downgrade drops the column, so the record's locks are lost; old copies still in
`plan_item` keep their own.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "student_course",
        sa.Column("locked", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        """
        UPDATE student_course s SET locked = true
        FROM plan_item i JOIN plan p ON p.id = i.plan_id
        WHERE p.is_primary AND p.account_id = s.account_id
          AND i.course_id = s.course_id AND i.term_id = s.term_id
          AND i.status IN ('completed', 'in_progress') AND i.locked
        """
    )


def downgrade() -> None:
    op.drop_column("student_course", "locked")
