"""stage3 add users.openid

Revision ID: 6a2d9c6a7e11
Revises: 3b1c2a9f1d2c
Create Date: 2025-12-18

说明：
- 新增 users.openid 列（小程序端必返）
- 新增 openid 唯一索引（openid 作为 unionid 缺失时的临时标识，也需要唯一）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "6a2d9c6a7e11"
down_revision = "3b1c2a9f1d2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("openid", sa.String(length=64), nullable=True, comment="微信 openid（小程序端必返）"))
    op.create_index("idx_users_openid_unique", "users", ["openid"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_users_openid_unique", table_name="users")
    op.drop_column("users", "openid")

