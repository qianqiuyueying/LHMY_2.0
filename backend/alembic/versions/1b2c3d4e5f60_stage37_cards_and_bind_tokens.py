"""stage37 cards and bind_tokens (H5 anonymous purchase + mini-program binding)

Revision ID: 1b2c3d4e5f60
Revises: 0f1e2d3c4b5a
Create Date: 2026-01-07

规格来源：
- specs/lhmy-2.0-maintenance/h5-anonymous-purchase-bind-token-v1.md

说明：
- 当前项目开发阶段允许清库，不考虑历史脏数据迁移兼容。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "1b2c3d4e5f60"
down_revision = "0f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("id", sa.String(length=36), nullable=False, comment="卡ID"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="状态：UNBOUND/BOUND"),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True, comment="归属用户ID（未绑定为空）"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cards_owner_user_id", "cards", ["owner_user_id"])

    op.create_table(
        "bind_tokens",
        sa.Column("token", sa.String(length=128), nullable=False, comment="绑定凭证 token"),
        sa.Column("card_id", sa.String(length=36), nullable=False, comment="卡ID"),
        sa.Column("expires_at", sa.DateTime(), nullable=False, comment="过期时间（UTC）"),
        sa.Column("used_at", sa.DateTime(), nullable=True, comment="已使用/作废时间（UTC）"),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index("idx_bind_tokens_card_id", "bind_tokens", ["card_id"])
    op.create_index("idx_bind_tokens_expires_at", "bind_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_bind_tokens_expires_at", table_name="bind_tokens")
    op.drop_index("idx_bind_tokens_card_id", table_name="bind_tokens")
    op.drop_table("bind_tokens")

    op.drop_index("idx_cards_owner_user_id", table_name="cards")
    op.drop_table("cards")


