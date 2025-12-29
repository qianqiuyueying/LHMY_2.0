"""stage21: notifications sending fields (admin manual send v1)

规格来源：
- specs/health-services-platform/admin-notifications-sending-v1.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7c1a2d3e4f5"
down_revision = "a1f4c2d8e6b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("sender_type", sa.String(length=32), nullable=True, comment="发送者类型（v1：ADMIN；历史系统通知可为空）"),
    )
    op.add_column(
        "notifications",
        sa.Column("sender_id", sa.String(length=36), nullable=True, comment="发送者ID（adminId，可空）"),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "category",
            sa.String(length=16),
            nullable=False,
            server_default="SYSTEM",
            comment="类别：SYSTEM/ACTIVITY/OPS",
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("meta_json", sa.JSON(), nullable=True, comment="扩展元数据（JSON，可空）"),
    )

    op.create_index("ix_notifications_receiver_type_id", "notifications", ["receiver_type", "receiver_id"], unique=False)
    op.create_index("ix_notifications_category", "notifications", ["category"], unique=False)
    op.create_index("ix_notifications_sender_type_id", "notifications", ["sender_type", "sender_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_sender_type_id", table_name="notifications")
    op.drop_index("ix_notifications_category", table_name="notifications")
    op.drop_index("ix_notifications_receiver_type_id", table_name="notifications")

    op.drop_column("notifications", "meta_json")
    op.drop_column("notifications", "category")
    op.drop_column("notifications", "sender_id")
    op.drop_column("notifications", "sender_type")

