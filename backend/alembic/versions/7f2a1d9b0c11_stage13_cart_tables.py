"""stage13 cart tables

Revision ID: 7f2a1d9b0c11
Revises: c2d8a1f6b3e1
Create Date: 2025-12-18

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-001（购物车后端 API）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "7f2a1d9b0c11"
down_revision = "c2d8a1f6b3e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="购物车ID"),
        sa.Column("user_id", sa.String(length=36), nullable=False, comment="用户ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
    )
    op.create_index("idx_carts_user_id_unique", "carts", ["user_id"], unique=True)

    op.create_table(
        "cart_items",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="购物车项ID"),
        sa.Column("cart_id", sa.String(length=36), nullable=False, comment="购物车ID"),
        sa.Column("item_type", sa.String(length=32), nullable=False, comment="类型：PRODUCT/VIRTUAL_VOUCHER/SERVICE_PACKAGE"),
        sa.Column("item_id", sa.String(length=36), nullable=False, comment="业务对象ID"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1", comment="数量"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.UniqueConstraint("cart_id", "item_type", "item_id", name="uq_cart_items_cart_item"),
    )
    op.create_index("idx_cart_items_cart_id", "cart_items", ["cart_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_cart_items_cart_id", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("idx_carts_user_id_unique", table_name="carts")
    op.drop_table("carts")

