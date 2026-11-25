"""Student record: the General Information columns, student_credit and student_course (Issue #14)

Revision ID: 0005
Revises: 0004

Adds the General Information answers to `student_profile`, the `working_notes` text, and the
account-level tables `student_credit` and `student_course`. Copies each account's primary
plan into the record: its credits, its completed and in-progress courses, and its entry term,
entry year level and graduation term (where the record has none yet). The plan rows are left
in place; saved plans now read credits and taken courses from the record, and the next save of
a plan removes its old copies. The old freeform columns stay until 0006 (Issue #16).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECKS = {
    "entry_year_level": "entry_year_level IS NULL OR entry_year_level BETWEEN 1 AND 4",
    "post_grad_plan": (
        "post_grad_plan IS NULL OR post_grad_plan IN "
        "('industry', 'grad_school', 'med_law', 'undecided')"
    ),
    "pace": "pace IS NULL OR pace IN ('early', 'on_time', 'flexible')",
    "courses_per_term": "courses_per_term IS NULL OR courses_per_term BETWEEN 1 AND 6",
    "theory_vs_application": (
        "theory_vs_application IS NULL OR theory_vs_application BETWEEN 1 AND 10"
    ),
}


def upgrade() -> None:
    columns = [
        sa.Column("expected_graduation_term", sa.String(length=7), nullable=True),
        sa.Column("entry_term", sa.String(length=7), nullable=True),
        sa.Column("entry_year_level", sa.SmallInteger(), nullable=True),
        sa.Column("post_grad_plan", sa.String(length=16), nullable=True),
        sa.Column("pace", sa.String(length=16), nullable=True),
        sa.Column("wants_research", sa.Boolean(), nullable=True),
        sa.Column("courses_per_term", sa.SmallInteger(), nullable=True),
        sa.Column("terms_away", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("class_formats", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("theory_vs_application", sa.SmallInteger(), nullable=True),
        sa.Column("working_notes", sa.Text(), nullable=True),
    ]
    for column in columns:
        op.add_column("student_profile", column)
    for name, check in _CHECKS.items():
        op.create_check_constraint(op.f(f"ck_student_profile_{name}"), "student_profile", check)

    op.create_table(
        "student_credit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("maps_to_course_id", sa.BigInteger(), nullable=True),
        sa.Column("units", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_student_credit_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["maps_to_course_id"],
            ["course.id"],
            name=op.f("fk_student_credit_maps_to_course_id_course"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_credit")),
    )
    op.create_index(
        op.f("ix_student_credit_account_id"), "student_credit", ["account_id"], unique=False
    )
    op.create_table(
        "student_course",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("term_id", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="completed", nullable=False),
        sa.Column("units", sa.Integer(), nullable=True),
        sa.Column("grading", sa.String(length=16), server_default="letter", nullable=False),
        sa.Column("grade", sa.String(length=4), nullable=True),
        sa.CheckConstraint(
            "status IN ('completed', 'in_progress')", name=op.f("ck_student_course_status")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_student_course_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["course.id"], name=op.f("fk_student_course_course_id_course")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_course")),
    )
    op.create_index(
        op.f("ix_student_course_account_id"), "student_course", ["account_id"], unique=False
    )

    # Copy each account's primary plan into its record.
    op.execute(
        """
        INSERT INTO student_profile (account_id)
        SELECT DISTINCT p.account_id FROM plan p WHERE p.is_primary
        ON CONFLICT (account_id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE student_profile sp
        SET entry_term = COALESCE(sp.entry_term, p.entry_term),
            entry_year_level = COALESCE(sp.entry_year_level, p.entry_year_level),
            expected_graduation_term = COALESCE(sp.expected_graduation_term, p.graduation_term)
        FROM plan p
        WHERE p.account_id = sp.account_id AND p.is_primary
        """
    )
    op.execute(
        """
        INSERT INTO student_credit (account_id, kind, label, maps_to_course_id, units)
        SELECT p.account_id, c.kind, c.label, c.maps_to_course_id, c.units
        FROM credit c JOIN plan p ON p.id = c.plan_id
        WHERE p.is_primary
        ORDER BY c.id
        """
    )
    op.execute(
        """
        INSERT INTO student_course (account_id, course_id, term_id, status, units, grading, grade)
        SELECT DISTINCT ON (p.account_id, i.course_id, i.term_id)
            p.account_id, i.course_id, i.term_id, i.status, i.units, i.grading, i.grade
        FROM plan_item i JOIN plan p ON p.id = i.plan_id
        WHERE p.is_primary AND i.course_id IS NOT NULL
          AND i.status IN ('completed', 'in_progress')
        ORDER BY p.account_id, i.course_id, i.term_id, i.id
        """
    )


def downgrade() -> None:
    # Copy the record back into each account's primary plan first (saved plans removed their own
    # copies after 0005). An account without a primary plan loses its credits and taken courses.
    op.execute(
        """
        DELETE FROM credit c USING plan p
        WHERE p.id = c.plan_id AND p.is_primary
          AND EXISTS (SELECT 1 FROM student_credit sc WHERE sc.account_id = p.account_id)
        """
    )
    op.execute(
        """
        INSERT INTO credit (plan_id, kind, label, maps_to_course_id, units)
        SELECT p.id, sc.kind, sc.label, sc.maps_to_course_id, sc.units
        FROM student_credit sc JOIN plan p ON p.account_id = sc.account_id AND p.is_primary
        ORDER BY sc.id
        """
    )
    op.execute(
        """
        INSERT INTO plan_item (plan_id, course_id, term_id, status, units, grading, grade)
        SELECT p.id, sc.course_id, sc.term_id, sc.status, sc.units, sc.grading, sc.grade
        FROM student_course sc JOIN plan p ON p.account_id = sc.account_id AND p.is_primary
        WHERE NOT EXISTS (
            SELECT 1 FROM plan_item i
            WHERE i.plan_id = p.id AND i.course_id = sc.course_id AND i.term_id = sc.term_id
        )
        ORDER BY sc.id
        """
    )
    op.drop_index(op.f("ix_student_course_account_id"), table_name="student_course")
    op.drop_table("student_course")
    op.drop_index(op.f("ix_student_credit_account_id"), table_name="student_credit")
    op.drop_table("student_credit")
    for name in _CHECKS:
        op.drop_constraint(op.f(f"ck_student_profile_{name}"), "student_profile", type_="check")
    for name in (
        "working_notes",
        "theory_vs_application",
        "class_formats",
        "terms_away",
        "courses_per_term",
        "wants_research",
        "pace",
        "post_grad_plan",
        "entry_year_level",
        "entry_term",
        "expected_graduation_term",
    ):
        op.drop_column("student_profile", name)
