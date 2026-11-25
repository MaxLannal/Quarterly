"""Remove the old per-plan copies of credits and taken courses (privacy review of the merge)

Revision ID: 0010
Revises: 0009

0005 copied each primary plan's credits and completed or in-progress courses into the student
record, but left the per-plan copies in `credit` and `plan_item`, for every plan, with their
grades. Nothing reads them since then (a saved plan shows the record), so they were invisible:
not shown, not in the account export, and still there after the student removed a course or a
grade on the dashboard. A plan removed its own copies only when it was saved again. This
removes them all. It runs after 0007, which reads their locks.

Downgrade restores nothing: 0005's downgrade copies the record back into each primary plan.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM credit")
    op.execute(
        "DELETE FROM plan_item WHERE course_id IS NOT NULL "
        "AND status IN ('completed', 'in_progress')"
    )


def downgrade() -> None:
    pass
