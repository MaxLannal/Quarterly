"""Drop `student_profile.feed_categories` (issue #19: the Feed and its focus chips are gone)

Revision ID: 0006_drop_feed_categories
Revises: 0005_drop_pathway

Other branches also add migrations after 0004: when they merge, set `down_revision` of the
first migration of the later branch to the newest one (issue #19 checklist item 15).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_drop_feed_categories"
down_revision: str | None = "0005_drop_pathway"
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
