"""权益规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性21：权益生成双形态完整性
- specs/health-services-platform/design.md -> 属性22：权益归属者唯一性（ownerId 唯一裁决字段）

目标：提供可测试的纯规则函数。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntitlementShape:
    owner_id: str
    qr_code: str
    voucher_code: str


def validate_entitlement_shape(e: EntitlementShape) -> None:
    """校验权益具备双形态且 ownerId 明确。"""

    if not e.owner_id:
        raise ValueError("ownerId 不能为空")
    if not e.qr_code:
        raise ValueError("qrCode 不能为空")
    if not e.voucher_code:
        raise ValueError("voucherCode 不能为空")
