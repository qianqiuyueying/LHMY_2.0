"""预约容量规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `CAPACITY_FULL`（容量不足）
- specs/health-services-platform/design.md -> 属性 19：预约取消状态恢复（释放容量）
- specs/health-services-platform/tasks.md -> 阶段6-36.2 / 37.3 / 39.3
"""

from __future__ import annotations


def can_reserve_capacity(*, remaining_capacity: int) -> bool:
    """是否还有可用容量。"""

    return int(remaining_capacity) > 0


def reserve_capacity(*, remaining_capacity: int) -> int:
    """扣减容量（调用方需确保 remaining_capacity>0）。"""

    rc = int(remaining_capacity)
    return rc - 1


def release_capacity(*, remaining_capacity: int, capacity: int) -> int:
    """释放容量（v1：不允许超过 capacity）。"""

    rc = int(remaining_capacity)
    cap = int(capacity)
    if cap < 0:
        cap = 0
    return min(cap, rc + 1)

