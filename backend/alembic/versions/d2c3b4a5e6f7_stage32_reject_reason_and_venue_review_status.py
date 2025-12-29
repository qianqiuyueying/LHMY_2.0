"""stage32: venue review status + reject reason for venues/products.

Revision ID: d2c3b4a5e6f7
Revises: b1c2d3e4f5a6
Create Date: 2025-12-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d2c3b4a5e6f7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "venues",
        sa.Column(
            "review_status",
            sa.String(length=16),
            nullable=False,
            server_default="DRAFT",
            comment="展示资料审核状态：DRAFT/SUBMITTED/APPROVED/REJECTED",
        ),
    )
    op.add_column(
        "venues",
        sa.Column("reject_reason", sa.String(length=512), nullable=True, comment="驳回原因（覆盖式）"),
    )
    op.add_column(
        "venues",
        sa.Column("rejected_at", sa.DateTime(), nullable=True, comment="驳回时间"),
    )

    op.add_column(
        "products",
        sa.Column("reject_reason", sa.String(length=512), nullable=True, comment="驳回原因（覆盖式）"),
    )
    op.add_column(
        "products",
        sa.Column("rejected_at", sa.DateTime(), nullable=True, comment="驳回时间"),
    )

    # 清理默认值（保持模型默认即可；避免 MySQL 表级默认长期存在）
    op.alter_column("venues", "review_status", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "rejected_at")
    op.drop_column("products", "reject_reason")
    op.drop_column("venues", "rejected_at")
    op.drop_column("venues", "reject_reason")
    op.drop_column("venues", "review_status")


