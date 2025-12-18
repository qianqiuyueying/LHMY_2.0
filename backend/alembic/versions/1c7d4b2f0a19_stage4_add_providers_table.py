"""stage4 add providers table

Revision ID: 1c7d4b2f0a19
Revises: 6a2d9c6a7e11
Create Date: 2025-12-18

规格来源：
- specs/health-services-platform/design.md -> 服务提供方主体（Provider，v1 最小可执行）

目的：
- 为 `GET /api/v1/products/{id}` 的 `provider.name` 提供稳定数据来源。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "1c7d4b2f0a19"
down_revision = "6a2d9c6a7e11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.String(length=36), primary_key=True, comment="服务提供方ID"),
        sa.Column("name", sa.String(length=256), nullable=False, comment="服务提供方名称"),
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


def downgrade() -> None:
    op.drop_table("providers")

