"""stage33: venue offline reason fields.

Revision ID: e3f4a5b6c7d8
Revises: d2c3b4a5e6f7
Create Date: 2025-12-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e3f4a5b6c7d8"
down_revision = "d2c3b4a5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column("offline_reason", sa.String(length=512), nullable=True, comment="下线原因（覆盖式）"),
    )
    op.add_column(
        "venues",
        sa.Column("offlined_at", sa.DateTime(), nullable=True, comment="下线时间"),
    )


def downgrade() -> None:
    op.drop_column("venues", "offlined_at")
    op.drop_column("venues", "offline_reason")


