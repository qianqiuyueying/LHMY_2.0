"""服务包展示格式（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 6：服务包展示格式一致性
- specs/health-services-platform/prototypes/h5.md -> 落地页展示：区域级别/等级/服务类别×次数

目标：
- 为各端提供一个“可复用、可测试”的展示格式生成函数，用于保证字段口径一致。
"""

from __future__ import annotations


def build_service_package_display(*, region_level: str, tier: str, services: list[tuple[str, int]]) -> str:
    """生成服务包展示文案（最小口径）。

    约束（v1）：
    - 必须包含：region_level、tier、以及 services 中每一项的“serviceType×次数”
    - services 不强制排序，但输出必须包含每一项（用于属性测试）
    """

    rl = str(region_level or "").strip().upper()
    tr = str(tier or "").strip()
    parts: list[str] = []
    for service_type, count in services:
        st = str(service_type or "").strip()
        c = int(count)
        parts.append(f"{st}×{c}")

    services_text = "、".join(parts)
    return f"{rl}｜{tr}｜{services_text}"
