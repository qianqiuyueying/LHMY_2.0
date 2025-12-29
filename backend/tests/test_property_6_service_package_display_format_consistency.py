"""属性测试：服务包展示格式一致性（属性6）。

规格来源：
- specs/health-services-platform/design.md -> 属性 6：服务包展示格式一致性
- specs/health-services-platform/tasks.md -> 阶段15-76.5（Property 6）

v1 最小断言：
- 对任意服务包展示格式，必须包含：区域级别、等级、以及每个服务类别×次数信息
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.service_package_display import build_service_package_display


@given(
    region_level=st.sampled_from(["CITY", "PROVINCE", "COUNTRY", "city", "province", "country"]),
    tier=st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True),
    services=st.lists(
        st.tuples(
            st.from_regex(r"[A-Za-z0-9_-]{1,64}", fullmatch=True),
            st.integers(min_value=1, max_value=9999),
        ),
        min_size=1,
        max_size=20,
        unique_by=lambda x: x[0],
    ),
)
def test_property_6_service_package_display_format_consistency(
    region_level: str, tier: str, services: list[tuple[str, int]]
):
    text = build_service_package_display(region_level=region_level, tier=tier, services=services)

    # 包含区域级别（大小写不敏感，函数会大写）
    assert str(region_level).strip().upper() in text
    # 包含等级
    assert str(tier).strip() in text
    # 包含服务类别×次数
    for service_type, count in services:
        assert f"{service_type}×{int(count)}" in text
