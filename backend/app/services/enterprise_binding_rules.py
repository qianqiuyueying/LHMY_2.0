"""企业绑定规则（v1 最小可执行口径）。

规格来源：
- specs/health-services-platform/design.md -> 属性10：企业绑定唯一性
- specs/health-services-platform/design.md -> 附录 B1：企业绑定状态迁移与约束

目标：提供可测试的纯规则函数，供后续绑定服务复用。
"""

from __future__ import annotations

from app.models.enums import UserEnterpriseBindingStatus


def can_submit_new_binding(existing_statuses: list[UserEnterpriseBindingStatus]) -> bool:
    """判断当前用户是否允许提交新的绑定申请。

    规则（属性10）：
    - 如果历史中存在 APPROVED：拒绝任何新的绑定申请
    - 如果仅存在 REJECTED（或为空）：允许重新提交
    """

    if UserEnterpriseBindingStatus.APPROVED in existing_statuses:
        return False
    return True
