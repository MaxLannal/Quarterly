"""review_rating: optional pace and grading strictness (Q11)

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_rating", sa.Column("pace", sa.SmallInteger(), nullable=True))
    op.add_column(
        "review_rating", sa.Column("grading_strictness", sa.SmallInteger(), nullable=True)
    )
    op.create_check_constraint("pace", "review_rating", "pace BETWEEN 1 AND 5")
    op.create_check_constraint("grading", "review_rating", "grading_strictness BETWEEN 1 AND 5")


def downgrade() -> None:
    op.drop_constraint("grading", "review_rating", type_="check")
    op.drop_constraint("pace", "review_rating", type_="check")
    op.drop_column("review_rating", "grading_strictness")
    op.drop_column("review_rating", "pace")
