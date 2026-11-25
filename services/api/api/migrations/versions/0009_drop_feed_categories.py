"""Drop `student_profile.feed_categories` (issue #19: the Feed and its focus chips are gone)

Revision ID: 0009
Revises: 0008

Issue #19 wrote this as 0006, after issue #15's migration. PR #21 merged first, so both follow
its 0005 to 0007 (issue #19 checklist item 15).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("student_profile", "feed_categories")


def downgrade() -> None:
    # The column as 0004 made it (empty: the saved focus categories are gone).
    op.add_column(
        "student_profile",
        sa.Column(
            "feed_categories",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
