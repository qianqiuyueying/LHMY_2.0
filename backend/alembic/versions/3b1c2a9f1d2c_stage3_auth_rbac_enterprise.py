"""stage3 auth/rbac/enterprise support

Revision ID: 3b1c2a9f1d2c
Revises: 94f73bae3568
Create Date: 2025-12-18

说明：
- 新增 admins 表（阶段3-17）
- users.phone / users.unionid 增加唯一索引（阶段3-16 一对一约束）
  - 注意：design.md 中示例使用了带 WHERE 的“部分唯一索引”，该语法是 PostgreSQL 风格；
    MySQL 8 不支持 partial index，但 MySQL 的 UNIQUE INDEX 对 NULL 值天然允许多行 NULL，
    因此直接创建唯一索引即可满足“非空唯一”的 v1 约束。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3b1c2a9f1d2c"
down_revision = "94f73bae3568"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="管理员ID"),
        sa.Column("username", sa.String(length=64), nullable=False, comment="登录用户名（唯一）"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="密码哈希（bcrypt）"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE", comment="状态：ACTIVE/SUSPENDED"),
        sa.Column("phone", sa.String(length=20), nullable=True, comment="手机号（用于2FA，可选）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        sa.UniqueConstraint("username", name="uq_admins_username"),
    )
    op.create_index("ix_admins_username", "admins", ["username"], unique=True)

    op.create_index("idx_users_phone_unique", "users", ["phone"], unique=True)
    op.create_index("idx_users_unionid_unique", "users", ["unionid"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_users_unionid_unique", table_name="users")
    op.drop_index("idx_users_phone_unique", table_name="users")

    op.drop_index("ix_admins_username", table_name="admins")
    op.drop_table("admins")

