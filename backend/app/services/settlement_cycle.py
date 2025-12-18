"""结算周期计算（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> SettlementRecord.cycle：v1 固定一种周期口径即可（例如 '2025-12' 或 '2025W51'）
- specs/health-services-platform/tasks.md -> 阶段7-45.3

v1 口径：
- 采用“自然月”作为结算周期：YYYY-MM（例如 2025-12）
"""

from __future__ import annotations

from datetime import datetime


def compute_settlement_cycle_monthly(*, dt: datetime) -> str:
    """将时间映射为结算周期标识（自然月：YYYY-MM）。

    注意：
    - v1 不区分时区，直接取传入 dt 的 year/month（调用方应确保 dt 已为正确时区口径）。
    """

    return f"{dt.year:04d}-{dt.month:02d}"

