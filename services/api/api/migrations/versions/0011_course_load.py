"""Replace `student_profile.courses_per_term` with `course_load`

Revision ID: 0011
Revises: 0010

Richard (2026-11-25): the guide asks for a course load (conservative, normal or ambitious), not
a number of courses per quarter. Most students mix 300-unit and 400-unit quarters, and 500 units
need the College's approval. A number of courses does not tell which load the student meant, so
the old answers are not carried over: the guide asks again.

A course in progress has no grade (Richard, 2026-11-25): a grade stored on one before is removed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_student_profile_courses_per_term"), "student_profile", type_="check"
    )
    op.drop_column("student_profile", "courses_per_term")
    op.add_column("student_profile", sa.Column("course_load", sa.String(16), nullable=True))
    op.create_check_constraint(
        op.f("ck_student_profile_course_load"),
        "student_profile",
        "course_load IS NULL OR course_load IN ('conservative', 'normal', 'ambitious')",
    )
    op.execute("UPDATE student_course SET grade = NULL WHERE status = 'in_progress'")


def downgrade() -> None:
    # The column as 0005 made it, empty: a load does not tell a number of courses.
    op.drop_constraint(op.f("ck_student_profile_course_load"), "student_profile", type_="check")
    op.drop_column("student_profile", "course_load")
    op.add_column(
        "student_profile", sa.Column("courses_per_term", sa.SmallInteger(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_student_profile_courses_per_term"),
        "student_profile",
        "courses_per_term IS NULL OR courses_per_term BETWEEN 1 AND 6",
    )
