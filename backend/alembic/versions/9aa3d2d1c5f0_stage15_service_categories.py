"""stage15: add service_categories table

规格来源：
- specs/health-services-platform/service-category-management.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9aa3d2d1c5f0"
down_revision = "4d9a7c1d2e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_categories",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="服务大类ID"),
        sa.Column("code", sa.String(length=64), nullable=False, comment="serviceType code"),
        sa.Column("display_name", sa.String(length=128), nullable=False, comment="中文展示名"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ENABLED", comment="状态：ENABLED/DISABLED"),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0", comment="排序（越大越靠前）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="更新时间",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_service_categories_code", "service_categories", ["code"], unique=True)
    op.create_index("ix_service_categories_status", "service_categories", ["status"], unique=False)
    op.create_index("ix_service_categories_sort", "service_categories", ["sort"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_service_categories_sort", table_name="service_categories")
    op.drop_index("ix_service_categories_status", table_name="service_categories")
    op.drop_index("ix_service_categories_code", table_name="service_categories")
    op.drop_table("service_categories")

