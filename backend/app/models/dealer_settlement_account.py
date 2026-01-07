from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.utils.datetime_utc import utcnow


class DealerSettlementAccount(Base):
    """经销商结算账户（v1 最小可用）。

    说明：
    - v1 先支持“银行卡打款”与“支付宝”两种；
    - 作为结算/打款的“长期账户信息”，结算单可在生成/打款时做快照。
    """

    __tablename__ = "dealer_settlement_accounts"

    dealer_id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="经销商ID（主键）")

    method: Mapped[str] = mapped_column(String(16), nullable=False, default="BANK", comment="打款方式：BANK/ALIPAY")

    account_name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="收款户名/实名")
    account_no: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="收款账号（银行卡/支付宝账号）")

    bank_name: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="开户行（BANK）")
    bank_branch: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="支行（BANK，可选）")

    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="联系人电话（可选）")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        comment="更新时间",
    )


