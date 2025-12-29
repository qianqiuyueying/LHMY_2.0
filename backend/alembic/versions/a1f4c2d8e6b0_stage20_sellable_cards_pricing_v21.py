"""stage20: sellable cards pricing v2.1

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md（v2.1：可售卡自带售价 priceOriginal；去掉计价商品依赖）
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1f4c2d8e6b0"
down_revision = "8c3e1d4a9b7f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) sellable_cards 增加 price_original（唯一售价）
    op.add_column(
        "sellable_cards",
        sa.Column(
            "price_original",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
            comment="可售卡唯一售价（元，v2.1）",
        ),
    )
    op.create_index("ix_sellable_cards_price_original", "sellable_cards", ["price_original"], unique=False)

    # 2) product_id 不再必填（v2.1 废弃计价商品依赖；保留兼容历史数据）
    op.alter_column("sellable_cards", "product_id", existing_type=sa.String(length=36), nullable=True)

    # 3) dealer_links.product_id 不再必填（v2.1：链接只需 sellableCardId）
    op.alter_column("dealer_links", "product_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    # downgrade：若存在 NULL product_id 可能失败，这里用占位 UUID 回填
    op.execute("UPDATE sellable_cards SET product_id = '00000000-0000-0000-0000-000000000000' WHERE product_id IS NULL")
    op.execute("UPDATE dealer_links SET product_id = '00000000-0000-0000-0000-000000000000' WHERE product_id IS NULL")

    op.alter_column("dealer_links", "product_id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column("sellable_cards", "product_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_index("ix_sellable_cards_price_original", table_name="sellable_cards")
    op.drop_column("sellable_cards", "price_original")

