"""stage25 booking order item source

Revision ID: f1c2d3e4a5b6
Revises: e2b9c1d7a8f4
Create Date: 2025-12-21

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f1c2d3e4a5b6"
down_revision = "e2b9c1d7a8f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) add new columns
    op.add_column(
        "bookings",
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="ENTITLEMENT", comment="来源"),
    )
    op.add_column("bookings", sa.Column("order_id", sa.String(length=36), nullable=True, comment="订单ID"))
    op.add_column("bookings", sa.Column("order_item_id", sa.String(length=36), nullable=True, comment="订单明细ID"))
    op.add_column("bookings", sa.Column("product_id", sa.String(length=36), nullable=True, comment="商品ID"))

    # 2) entitlement_id becomes nullable (support ORDER_ITEM booking)
    op.alter_column("bookings", "entitlement_id", existing_type=sa.String(length=36), nullable=True)

    # 3) indexes
    op.create_index("ix_bookings_source_type", "bookings", ["source_type"])
    op.create_index("ix_bookings_order_id", "bookings", ["order_id"])
    op.create_index("ix_bookings_order_item_id", "bookings", ["order_item_id"])
    op.create_index("ix_bookings_product_id", "bookings", ["product_id"])

    # 4) drop server default
    op.alter_column("bookings", "source_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_bookings_product_id", table_name="bookings")
    op.drop_index("ix_bookings_order_item_id", table_name="bookings")
    op.drop_index("ix_bookings_order_id", table_name="bookings")
    op.drop_index("ix_bookings_source_type", table_name="bookings")

    op.alter_column("bookings", "entitlement_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_column("bookings", "product_id")
    op.drop_column("bookings", "order_item_id")
    op.drop_column("bookings", "order_id")
    op.drop_column("bookings", "source_type")


