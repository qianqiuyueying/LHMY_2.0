"""stage36 phone uniqueness (admin 2FA + provider/dealer register)

Revision ID: 0f1e2d3c4b5a
Revises: f3b4c5d6e7f8
Create Date: 2026-01-07

规格来源：
- specs-prod/admin/api-contracts.md
  - 2.7 Admin Phone Bind：admins.phone 全局唯一
  - 2A/2B register：provider_users.phone / dealer_users.phone 角色内唯一（跨角色允许重复）

说明：
- 当前项目开发阶段允许清库，不考虑历史脏数据迁移兼容。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0f1e2d3c4b5a"
down_revision = "f3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Admin 2FA phone：全局唯一（允许 NULL，多行 NULL 在 MySQL UNIQUE 下合法）
    op.create_index("idx_admins_phone_unique", "admins", ["phone"], unique=True)

    # Provider register phone：角色内唯一（provider_users 域内）
    op.add_column(
        "provider_users",
        sa.Column("phone", sa.String(length=32), nullable=True, comment="注册手机号（角色内唯一，可选）"),
    )
    op.create_index("idx_provider_users_phone_unique", "provider_users", ["phone"], unique=True)

    # Dealer register phone：角色内唯一（dealer_users 域内）
    op.add_column(
        "dealer_users",
        sa.Column("phone", sa.String(length=32), nullable=True, comment="注册手机号（角色内唯一，可选）"),
    )
    op.create_index("idx_dealer_users_phone_unique", "dealer_users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_dealer_users_phone_unique", table_name="dealer_users")
    op.drop_column("dealer_users", "phone")

    op.drop_index("idx_provider_users_phone_unique", table_name="provider_users")
    op.drop_column("provider_users", "phone")

    op.drop_index("idx_admins_phone_unique", table_name="admins")


