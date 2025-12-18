"""价格裁决（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性12：价格优先级计算一致性
- specs/health-services-platform/tasks.md -> 阶段2-6.5

优先级：活动价 > 会员价 > 员工价 > 原价
"""

from __future__ import annotations

from typing import Any


def resolve_price(price: dict[str, Any]) -> float:
    """按优先级选择最终价格。

    约定：price 结构形如：
    { original: number, employee?: number, member?: number, activity?: number }

    注意：v1 仅实现优先级裁决，不处理货币精度/折扣叠加等扩展口径。
    """

    for key in ("activity", "member", "employee", "original"):
        v = price.get(key)
        if v is None:
            continue
        return float(v)

    raise ValueError("price.original 不能为空")
