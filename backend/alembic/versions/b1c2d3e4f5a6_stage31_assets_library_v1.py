"""stage31: assets library v1 (image).

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f6
Create Date: 2025-12-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False, comment="资产ID"),
        sa.Column("kind", sa.String(length=16), nullable=False, comment="类型：IMAGE"),
        sa.Column("sha256", sa.String(length=64), nullable=False, comment="内容哈希（sha256）"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, comment="文件大小（bytes）"),
        sa.Column("mime", sa.String(length=64), nullable=False, comment="MIME"),
        sa.Column("ext", sa.String(length=16), nullable=False, comment="扩展名"),
        sa.Column("storage", sa.String(length=16), nullable=False, comment="存储：LOCAL/OSS(预留)"),
        sa.Column("storage_key", sa.Text(), nullable=False, comment="存储 key（如 uploads/2025/12/xxx.jpg）"),
        sa.Column("url", sa.Text(), nullable=False, comment="对外 URL（/static/uploads/... 或 https://cdn/...）"),
        sa.Column("original_filename", sa.String(length=256), nullable=False, comment="原文件名（可选）"),
        sa.Column("created_by_actor_type", sa.String(length=16), nullable=False, comment="创建者类型"),
        sa.Column("created_by_actor_id", sa.String(length=36), nullable=False, comment="创建者ID"),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assets_kind"), "assets", ["kind"], unique=False)
    op.create_index(op.f("ix_assets_sha256"), "assets", ["sha256"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_sha256"), table_name="assets")
    op.drop_index(op.f("ix_assets_kind"), table_name="assets")
    op.drop_table("assets")


