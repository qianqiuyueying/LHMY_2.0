"""stage30: cms_contents allow nullable channel_id (content center vs delivery split).

Revision ID: a0b1c2d3e4f6
Revises: ef12ab34cd56
Create Date: 2025-12-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a0b1c2d3e4f6"
down_revision = "ef12ab34cd56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "cms_contents",
        "channel_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )


def downgrade() -> None:
    # best-effort: replace NULL with empty string before making it NOT NULL again
    op.execute("UPDATE cms_contents SET channel_id = '' WHERE channel_id IS NULL")
    op.alter_column(
        "cms_contents",
        "channel_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )


