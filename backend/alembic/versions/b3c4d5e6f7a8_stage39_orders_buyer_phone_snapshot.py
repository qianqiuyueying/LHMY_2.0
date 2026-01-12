"""stage39: orders add buyer_phone snapshot for anonymous service package purchases.

Revision ID: b3c4d5e6f7a8
Revises: a9b8c7d6e5f4
Create Date: 2026-01-09

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ADMIN-P1-019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "buyer_phone",
            sa.String(length=32),
            nullable=True,
            comment="买家手机号快照（用于 H5 匿名购卡订单；对外返回仅脱敏）",
        ),
    )
    op.create_index(op.f("ix_orders_buyer_phone"), "orders", ["buyer_phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_buyer_phone"), table_name="orders")
    op.drop_column("orders", "buyer_phone")

