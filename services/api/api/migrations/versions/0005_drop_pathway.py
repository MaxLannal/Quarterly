"""Drop the dashboard routes table `pathway` (issue #15: "Your routes" removed)

Revision ID: 0005_drop_pathway
Revises: 0004

Other branches also add migrations after 0004: when they merge, the later one sets its
`down_revision` to the newest migration (issue #15 checklist item 21).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_drop_pathway"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_pathway_one_chosen", table_name="pathway", postgresql_where=sa.text("status = 'chosen'")
    )
    op.drop_index(op.f("ix_pathway_account_id"), table_name="pathway")
    op.drop_table("pathway")


def downgrade() -> None:
    # The table as 0004 made it (empty: the routes that were in it are gone).
    op.create_table(
        "pathway",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="major", nullable=False),
        sa.Column("program_ids", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column(
            "courses", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False
        ),
        sa.Column(
            "milestones",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "fit", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("origin", sa.String(length=8), server_default="ai", nullable=False),
        sa.Column("position", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("updated_day", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.CheckConstraint("origin IN ('ai', 'user')", name=op.f("ck_pathway_origin")),
        sa.CheckConstraint(
            "status IN ('open', 'chosen', 'archived')", name=op.f("ck_pathway_status")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["account.id"],
            name=op.f("fk_pathway_account_id_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pathway")),
    )
    op.create_index(op.f("ix_pathway_account_id"), "pathway", ["account_id"], unique=False)
    op.create_index(
        "uq_pathway_one_chosen",
        "pathway",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'chosen'"),
    )
