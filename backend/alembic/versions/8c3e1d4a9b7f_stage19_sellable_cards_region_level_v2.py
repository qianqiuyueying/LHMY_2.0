"""stage19: sellable cards v2 regionLevel

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2：可售卡只配置 regionLevel）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "8c3e1d4a9b7f"
down_revision = "5a2d1f7c8b14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # v2：新增 region_level；兼容历史数据从 region_scope 推断
    op.add_column(
        "sellable_cards",
        sa.Column(
            "region_level",
            sa.String(length=16),
            nullable=False,
            server_default="CITY",
            comment="卡片区域级别：CITY/PROVINCE/COUNTRY",
        ),
    )
    op.create_index("ix_sellable_cards_region_level", "sellable_cards", ["region_level"], unique=False)

    # v2：region_scope 不再必填（可售卡不配置具体区域）
    op.alter_column("sellable_cards", "region_scope", existing_type=sa.String(length=64), nullable=True)

    # backfill：若 region_scope 形如 "CITY:xxxx" 则提取前缀；否则保持默认 CITY
    op.execute(
        """
        UPDATE sellable_cards
        SET region_level = UPPER(SUBSTRING_INDEX(region_scope, ':', 1))
        WHERE region_scope IS NOT NULL AND region_scope LIKE '%:%'
        """
    )

    # 规范化：仅允许 CITY/PROVINCE/COUNTRY；其他值回退 CITY
    op.execute(
        """
        UPDATE sellable_cards
        SET region_level = 'CITY'
        WHERE region_level NOT IN ('CITY','PROVINCE','COUNTRY')
        """
    )


def downgrade() -> None:
    # downgrade：把 region_scope 改回 NOT NULL 可能失败（若已有 NULL），这里先回填空值为 'CITY:000000'
    op.execute("UPDATE sellable_cards SET region_scope = 'CITY:000000' WHERE region_scope IS NULL")
    op.alter_column("sellable_cards", "region_scope", existing_type=sa.String(length=64), nullable=False)

    op.drop_index("ix_sellable_cards_region_level", table_name="sellable_cards")
    op.drop_column("sellable_cards", "region_level")

