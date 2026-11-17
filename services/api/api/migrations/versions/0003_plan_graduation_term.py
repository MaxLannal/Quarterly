"""plan: graduation_term (FEEDBACK "Number of Years")

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plan", sa.Column("graduation_term", sa.String(length=7), nullable=True))


def downgrade() -> None:
    op.drop_column("plan", "graduation_term")
