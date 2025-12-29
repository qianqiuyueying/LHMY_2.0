"""stage16: sellable cards for dealer links

规格来源：
- specs/health-services-platform/dealer-link-sellable-cards-v1.md
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c7b6a19f3c21"
down_revision = "9aa3d2d1c5f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sellable_cards",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False, comment="可售卡ID（sellableCardId）"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="展示名（例如：健身市卡-北京）"),
        sa.Column("product_id", sa.String(length=36), nullable=False, comment="高端服务卡商品ID"),
        sa.Column("service_package_template_id", sa.String(length=36), nullable=False, comment="服务包模板ID"),
        sa.Column("region_scope", sa.String(length=64), nullable=False, comment="区域范围（例如 CITY:110100）"),
        sa.Column("tier", sa.String(length=64), nullable=True, comment="等级覆盖（可选）"),
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
    op.create_index("ix_sellable_cards_status", "sellable_cards", ["status"], unique=False)
    op.create_index("ix_sellable_cards_sort", "sellable_cards", ["sort"], unique=False)
    op.create_index("ix_sellable_cards_product_id", "sellable_cards", ["product_id"], unique=False)
    op.create_index("ix_sellable_cards_template_id", "sellable_cards", ["service_package_template_id"], unique=False)

    # dealer_links 增加 sellable_card_id（可为空，保持向后兼容）
    op.add_column(
        "dealer_links",
        sa.Column("sellable_card_id", sa.String(length=36), nullable=True, comment="可售卡ID（sellableCardId，可为空）"),
    )
    op.create_index("ix_dealer_links_sellable_card_id", "dealer_links", ["sellable_card_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dealer_links_sellable_card_id", table_name="dealer_links")
    op.drop_column("dealer_links", "sellable_card_id")

    op.drop_index("ix_sellable_cards_template_id", table_name="sellable_cards")
    op.drop_index("ix_sellable_cards_product_id", table_name="sellable_cards")
    op.drop_index("ix_sellable_cards_sort", table_name="sellable_cards")
    op.drop_index("ix_sellable_cards_status", table_name="sellable_cards")
    op.drop_table("sellable_cards")

