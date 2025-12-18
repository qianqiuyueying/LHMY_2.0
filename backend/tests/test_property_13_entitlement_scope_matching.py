"""属性测试：权益类型和适用范围匹配（属性13）。

规格来源：
- specs/health-services-platform/design.md -> 属性 13：权益类型和适用范围匹配
- specs/health-services-platform/tasks.md -> 阶段5-33.3

v1 最小断言：
- entitlementType=VOUCHER：全平台通用（不做区域限制）
- entitlementType=SERVICE_PACKAGE：必须匹配 applicableRegions 与场所归属地区字段（CITY/PROVINCE/COUNTRY）
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import EntitlementType
from app.services.entitlement_scope_rules import is_entitlement_eligible_for_venue


_CITY = "CITY:110100"
_PROVINCE = "PROVINCE:110000"
_COUNTRY = "COUNTRY:CN"


@given(
    venue_id=st.text(min_size=1, max_size=36),
    random_regions=st.lists(st.text(min_size=1, max_size=32), max_size=5),
)
def test_property_13_voucher_is_universal(venue_id: str, random_regions: list[str]):
    assert (
        is_entitlement_eligible_for_venue(
            entitlement_type=EntitlementType.VOUCHER.value,
            applicable_regions=random_regions,
            applicable_venues=None,
            venue_id=venue_id,
            venue_country_code=None,
            venue_province_code=None,
            venue_city_code=None,
        )
        is True
    )


def test_property_13_service_package_must_match_region_city():
    assert (
        is_entitlement_eligible_for_venue(
            entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
            applicable_regions=[_CITY],
            applicable_venues=None,
            venue_id="v1",
            venue_country_code=_COUNTRY,
            venue_province_code=_PROVINCE,
            venue_city_code=_CITY,
        )
        is True
    )
    assert (
        is_entitlement_eligible_for_venue(
            entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
            applicable_regions=[_CITY],
            applicable_venues=None,
            venue_id="v2",
            venue_country_code=_COUNTRY,
            venue_province_code=_PROVINCE,
            venue_city_code="CITY:999999",
        )
        is False
    )

