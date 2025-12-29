"""stage26 cms content publish scopes

Revision ID: ab12cd34ef56
Revises: f1c2d3e4a5b6
Create Date: 2025-12-22

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "f1c2d3e4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # v2：CMS 内容按渠道发布（官网/小程序）
    op.add_column(
        "cms_contents",
        sa.Column(
            "mp_status",
            sa.String(length=16),
            nullable=False,
            server_default="DRAFT",
            comment="小程序状态：DRAFT/PUBLISHED/OFFLINE",
        ),
    )
    op.add_column("cms_contents", sa.Column("mp_published_at", sa.DateTime(), nullable=True, comment="小程序发布时间"))

    # 兼容：历史数据（原来 status=PUBLISHED 的内容默认也对小程序可见）
    op.execute("UPDATE cms_contents SET mp_status = status, mp_published_at = published_at")

    # 清理默认值（保持应用层默认）
    op.alter_column("cms_contents", "mp_status", server_default=None)


def downgrade() -> None:
    op.drop_column("cms_contents", "mp_published_at")
    op.drop_column("cms_contents", "mp_status")


