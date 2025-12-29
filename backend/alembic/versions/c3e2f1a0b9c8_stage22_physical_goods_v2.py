"""stage22: physical goods v2 (address book + stock reservation + shipping fields)

规格来源：
- specs/health-services-platform/tasks.md -> REQ-ECOMMERCE-P0-001（物流商品 v2）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "c3e2f1a0b9c8"
down_revision = "b7c1a2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_addresses
    op.create_table(
        "user_addresses",
        sa.Column("id", sa.String(length=36), nullable=False, comment="地址ID"),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="用户ID"),
        sa.Column("receiver_name", sa.String(length=64), nullable=False, comment="收件人姓名"),
        sa.Column("receiver_phone", sa.String(length=32), nullable=False, comment="收件人手机号"),
        sa.Column("country_code", sa.String(length=32), nullable=True, comment="国家编码（如 COUNTRY:CN）"),
        sa.Column("province_code", sa.String(length=32), nullable=True, comment="省编码（如 PROVINCE:110000）"),
        sa.Column("city_code", sa.String(length=32), nullable=True, comment="市编码（如 CITY:110100）"),
        sa.Column("district_code", sa.String(length=32), nullable=True, comment="区县编码（可选）"),
        sa.Column("address_line", sa.String(length=256), nullable=False, comment="详细地址"),
        sa.Column("postal_code", sa.String(length=16), nullable=True, comment="邮编"),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="是否默认地址",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_addresses_user_id"), "user_addresses", ["user_id"], unique=False)
    op.create_index("ix_user_addresses_user_default", "user_addresses", ["user_id", "is_default"], unique=False)

    # products: inventory + shipping fee
    op.add_column(
        "products",
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="库存（总）"),
    )
    op.add_column(
        "products",
        sa.Column(
            "reserved_stock",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="已占用库存（待支付预占）",
        ),
    )
    op.add_column("products", sa.Column("weight", sa.Float(), nullable=True, comment="重量（可选）"))
    op.add_column(
        "products",
        sa.Column("shipping_fee", sa.Float(), nullable=False, server_default=sa.text("0"), comment="固定运费（v2 最小）"),
    )

    # orders: fulfillment + shipping snapshot
    op.add_column("orders", sa.Column("fulfillment_type", sa.String(length=32), nullable=True, comment="履约类型：SERVICE/PHYSICAL_GOODS"))
    op.add_column(
        "orders",
        sa.Column(
            "fulfillment_status",
            sa.String(length=32),
            nullable=True,
            comment="物流状态：NOT_SHIPPED/SHIPPED/DELIVERED/RECEIVED（仅物流商品）",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("goods_amount", sa.Float(), nullable=False, server_default=sa.text("0"), comment="商品金额（不含运费）"),
    )
    op.add_column(
        "orders",
        sa.Column("shipping_amount", sa.Float(), nullable=False, server_default=sa.text("0"), comment="运费金额"),
    )
    op.add_column("orders", sa.Column("shipping_address_json", mysql.JSON(), nullable=True, comment="收货地址快照（JSON）"))
    op.add_column("orders", sa.Column("reservation_expires_at", sa.DateTime(), nullable=True, comment="库存占用到期时间（待支付超时释放）"))

    op.add_column("orders", sa.Column("shipping_carrier", sa.String(length=64), nullable=True, comment="快递公司"))
    op.add_column("orders", sa.Column("shipping_tracking_no", sa.String(length=64), nullable=True, comment="运单号"))
    op.add_column("orders", sa.Column("shipped_at", sa.DateTime(), nullable=True, comment="发货时间"))
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(), nullable=True, comment="妥投时间"))
    op.add_column("orders", sa.Column("received_at", sa.DateTime(), nullable=True, comment="确认收货时间"))

    op.create_index("ix_orders_fulfillment_type", "orders", ["fulfillment_type"], unique=False)
    op.create_index("ix_orders_fulfillment_status", "orders", ["fulfillment_status"], unique=False)
    op.create_index("ix_orders_reservation_expires_at", "orders", ["reservation_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_reservation_expires_at", table_name="orders")
    op.drop_index("ix_orders_fulfillment_status", table_name="orders")
    op.drop_index("ix_orders_fulfillment_type", table_name="orders")

    op.drop_column("orders", "received_at")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "shipped_at")
    op.drop_column("orders", "shipping_tracking_no")
    op.drop_column("orders", "shipping_carrier")
    op.drop_column("orders", "reservation_expires_at")
    op.drop_column("orders", "shipping_address_json")
    op.drop_column("orders", "shipping_amount")
    op.drop_column("orders", "goods_amount")
    op.drop_column("orders", "fulfillment_status")
    op.drop_column("orders", "fulfillment_type")

    op.drop_column("products", "shipping_fee")
    op.drop_column("products", "weight")
    op.drop_column("products", "reserved_stock")
    op.drop_column("products", "stock")

    op.drop_index("ix_user_addresses_user_default", table_name="user_addresses")
    op.drop_index(op.f("ix_user_addresses_user_id"), table_name="user_addresses")
    op.drop_table("user_addresses")


