"""权益状态机（REQ-P1-005）。

规格来源：
- specs/health-services-platform/后端升级需求与变更清单（v1）.md -> REQ-P1-005
- specs/health-services-platform/design.md -> 权益状态（ACTIVE/USED/EXPIRED/REFUNDED/TRANSFERRED）
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.enums import EntitlementStatus


_ALLOWED: dict[str, set[str]] = {
    EntitlementStatus.ACTIVE.value: {
        EntitlementStatus.USED.value,
        EntitlementStatus.EXPIRED.value,
        EntitlementStatus.REFUNDED.value,
        EntitlementStatus.TRANSFERRED.value,
    },
    EntitlementStatus.USED.value: set(),
    EntitlementStatus.EXPIRED.value: set(),
    EntitlementStatus.REFUNDED.value: set(),
    EntitlementStatus.TRANSFERRED.value: set(),
}


def assert_entitlement_status_transition(*, current: str, target: str) -> None:
    allowed = _ALLOWED.get(str(current), set())
    if str(target) not in allowed:
        raise HTTPException(status_code=409, detail={"code": "STATE_CONFLICT", "message": "权益状态不允许变更"})

