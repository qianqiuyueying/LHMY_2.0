"""stage34: order item unit price type.

Revision ID: f2a3b4c5d6e7
Revises: e3f4a5b6c7d8
Create Date: 2025-12-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f2a3b4c5d6e7"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 价格来源：activity/member/employee/original（默认 original，兼容历史数据）
    op.add_column(
        "order_items",
        sa.Column(
            "unit_price_type",
            sa.String(length=16),
            nullable=False,
            server_default="original",
            comment="单价来源：activity/member/employee/original",
        ),
    )


def downgrade() -> None:
    op.drop_column("order_items", "unit_price_type")


