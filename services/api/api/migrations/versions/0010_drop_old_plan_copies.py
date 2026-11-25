"""Remove the old per-plan copies of credits and taken courses (privacy review of the merge)

Revision ID: 0010
Revises: 0009

0005 copied each primary plan's credits and completed or in-progress courses into the student
record, but left the per-plan copies in `credit` and `plan_item`, for every plan, with their
grades. Nothing reads them since then (a saved plan shows the record), so they were invisible:
not shown, not in the account export, and still there after the student removed a course or a
grade on the dashboard. A plan removed its own copies only when it was saved again. This
removes them all. It runs after 0007, which reads their locks.

0005 filled the record from the primary plan only. An account with saved plans but no primary
plan then kept its credits and taken courses only in these copies, so first such an empty
record is filled from the account's most recently updated plan, as 0005 did.

Downgrade restores nothing: 0005's downgrade copies the record back into each primary plan.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: For each account whose record is still empty: its most recently updated plan.
_SOURCE = """
    CREATE TEMPORARY TABLE record_source AS
    SELECT DISTINCT ON (p.account_id) p.account_id, p.id AS plan_id
    FROM plan p
    WHERE NOT EXISTS (SELECT 1 FROM student_credit c WHERE c.account_id = p.account_id)
      AND NOT EXISTS (SELECT 1 FROM student_course s WHERE s.account_id = p.account_id)
    ORDER BY p.account_id, p.is_primary DESC, p.updated_day DESC, p.id
"""


def upgrade() -> None:
    op.execute(_SOURCE)
    op.execute(
        """
        INSERT INTO student_credit (account_id, kind, label, maps_to_course_id, units)
        SELECT r.account_id, c.kind, c.label, c.maps_to_course_id, c.units
        FROM credit c JOIN record_source r ON r.plan_id = c.plan_id
        ORDER BY c.id
        """
    )
    op.execute(
        """
        INSERT INTO student_course
            (account_id, course_id, term_id, status, units, grading, grade, locked)
        SELECT DISTINCT ON (r.account_id, i.course_id, i.term_id)
            r.account_id, i.course_id, i.term_id, i.status, i.units, i.grading, i.grade, i.locked
        FROM plan_item i JOIN record_source r ON r.plan_id = i.plan_id
        WHERE i.course_id IS NOT NULL AND i.status IN ('completed', 'in_progress')
        ORDER BY r.account_id, i.course_id, i.term_id, i.id
        """
    )
    op.execute("DROP TABLE record_source")
    op.execute("DELETE FROM credit")
    op.execute(
        "DELETE FROM plan_item WHERE course_id IS NOT NULL "
        "AND status IN ('completed', 'in_progress')"
    )


def downgrade() -> None:
    pass
