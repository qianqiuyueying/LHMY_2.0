"""stage24: dealer settlement account + settlement payout fields

Revision ID: e2b9c1d7a8f4
Revises: d1a4b0c9e2f3
Create Date: 2025-12-21

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "e2b9c1d7a8f4"
down_revision = "d1a4b0c9e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dealer_settlement_accounts",
        sa.Column("dealer_id", sa.String(length=36), nullable=False, comment="经销商ID（主键）"),
        sa.Column("method", sa.String(length=16), nullable=False, server_default="BANK", comment="打款方式：BANK/ALIPAY"),
        sa.Column("account_name", sa.String(length=128), nullable=False, server_default="", comment="收款户名/实名"),
        sa.Column("account_no", sa.String(length=64), nullable=False, server_default="", comment="收款账号（银行卡/支付宝账号）"),
        sa.Column("bank_name", sa.String(length=128), nullable=True, comment="开户行（BANK）"),
        sa.Column("bank_branch", sa.String(length=128), nullable=True, comment="支行（BANK，可选）"),
        sa.Column("contact_phone", sa.String(length=32), nullable=True, comment="联系人电话（可选）"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"), comment="更新时间"),
        sa.PrimaryKeyConstraint("dealer_id"),
    )

    op.add_column("settlement_records", sa.Column("payout_method", sa.String(length=16), nullable=True, comment="打款方式快照：BANK/ALIPAY"))
    op.add_column("settlement_records", sa.Column("payout_account_json", mysql.JSON(), nullable=True, comment="打款账户快照（JSON）"))
    op.add_column("settlement_records", sa.Column("payout_reference", sa.String(length=128), nullable=True, comment="打款流水号/参考号"))
    op.add_column("settlement_records", sa.Column("payout_note", sa.String(length=512), nullable=True, comment="打款备注"))
    op.add_column("settlement_records", sa.Column("payout_marked_by", sa.String(length=36), nullable=True, comment="标记打款的管理员ID"))
    op.add_column("settlement_records", sa.Column("payout_marked_at", sa.DateTime(), nullable=True, comment="标记打款时间"))


def downgrade() -> None:
    op.drop_column("settlement_records", "payout_marked_at")
    op.drop_column("settlement_records", "payout_marked_by")
    op.drop_column("settlement_records", "payout_note")
    op.drop_column("settlement_records", "payout_reference")
    op.drop_column("settlement_records", "payout_account_json")
    op.drop_column("settlement_records", "payout_method")
    op.drop_table("dealer_settlement_accounts")


