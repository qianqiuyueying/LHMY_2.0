"""stage14 dealer auth tables

Revision ID: 4d9a7c1d2e0f
Revises: 7f2a1d9b0c11
Create Date: 2025-12-19

规格来源：
- specs/功能实现/admin/tasks.md -> T-A02（Dealer 账号获取/创建 + 登录）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "4d9a7c1d2e0f"
down_revision = "7f2a1d9b0c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dealer_users",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="经销商后台账号ID"),
        sa.Column("dealer_id", sa.String(length=36), nullable=False, comment="经销商主体ID"),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True, comment="登录用户名（唯一）"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="密码哈希（bcrypt）"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE", comment="状态：ACTIVE/SUSPENDED"),
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
    op.create_index("idx_dealer_users_username_unique", "dealer_users", ["username"], unique=True)
    op.create_index("idx_dealer_users_dealer_id", "dealer_users", ["dealer_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_dealer_users_dealer_id", table_name="dealer_users")
    op.drop_index("idx_dealer_users_username_unique", table_name="dealer_users")
    op.drop_table("dealer_users")

