"""stage12 provider auth tables

Revision ID: c2d8a1f6b3e1
Revises: 1c7d4b2f0a19
Create Date: 2025-12-18

规格来源：
- specs/health-services-platform/design.md -> RBAC：阶段12落地 PROVIDER/PROVIDER_STAFF 账号体系
- specs/health-services-platform/tasks.md -> 阶段12「Provider 认证（v1）」
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c2d8a1f6b3e1"
down_revision = "1c7d4b2f0a19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_users",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="服务提供方后台账号ID"),
        sa.Column("provider_id", sa.String(length=36), nullable=False, index=True, comment="服务提供方主体ID"),
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
    op.create_index("idx_provider_users_username_unique", "provider_users", ["username"], unique=True)
    op.create_index("idx_provider_users_provider_id", "provider_users", ["provider_id"], unique=False)

    op.create_table(
        "provider_staff",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="服务提供方员工账号ID"),
        sa.Column("provider_id", sa.String(length=36), nullable=False, index=True, comment="服务提供方主体ID"),
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
    op.create_index("idx_provider_staff_username_unique", "provider_staff", ["username"], unique=True)
    op.create_index("idx_provider_staff_provider_id", "provider_staff", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_provider_staff_provider_id", table_name="provider_staff")
    op.drop_index("idx_provider_staff_username_unique", table_name="provider_staff")
    op.drop_table("provider_staff")

    op.drop_index("idx_provider_users_provider_id", table_name="provider_users")
    op.drop_index("idx_provider_users_username_unique", table_name="provider_users")
    op.drop_table("provider_users")

