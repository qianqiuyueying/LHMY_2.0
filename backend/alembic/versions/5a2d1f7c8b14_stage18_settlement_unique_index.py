"""stage18: unique index for dealer settlements

规格来源：
- specs/health-services-platform/dealer-settlement-v1.md（同 cycle + dealerId 幂等）
"""

from __future__ import annotations

from alembic import op


revision = "5a2d1f7c8b14"
down_revision = "2f1c0b9a6c02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # v1：保证同一经销商同一周期只会有一条结算单（生成幂等/防重复）
    op.create_index(
        "ux_settlement_records_dealer_cycle",
        "settlement_records",
        ["dealer_id", "cycle"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_settlement_records_dealer_cycle", table_name="settlement_records")

