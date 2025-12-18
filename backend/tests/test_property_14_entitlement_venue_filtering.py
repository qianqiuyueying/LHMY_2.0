"""属性测试：权益使用场所过滤正确性（属性14）。

规格来源：
- specs/health-services-platform/design.md -> 属性 14：权益使用场所过滤正确性
- specs/health-services-platform/tasks.md -> 阶段6-35.4

v1 最小断言：
- entitlementType=VOUCHER：全平台通用，但若配置了 applicableVenues（白名单）则必须命中才可用
- entitlementType=SERVICE_PACKAGE：必须匹配 applicableRegions（区域限制），且若配置了 applicableVenues 则也必须命中
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import EntitlementType
from app.services.venue_filtering_rules import VenueLite, VenueRegion, filter_venues_by_entitlement


@given(
    venue_ids=st.lists(st.text(min_size=1, max_size=36), min_size=1, max_size=20, unique=True),
    whitelist=st.lists(st.integers(min_value=0, max_value=19), max_size=20),
    random_regions=st.lists(st.text(min_size=1, max_size=32), max_size=5),
)
def test_property_14_voucher_only_respects_applicable_venues(
    venue_ids: list[str],
    whitelist: list[int],
    random_regions: list[str],
):
    venues = [
        VenueLite(id=vid, region=VenueRegion(country_code=None, province_code=None, city_code=None)) for vid in venue_ids
    ]
    picked = {venue_ids[i] for i in whitelist if i < len(venue_ids)}
    applicable_venues = list(picked)

    filtered = filter_venues_by_entitlement(
        venues=venues,
        entitlement_type=EntitlementType.VOUCHER.value,
        applicable_regions=random_regions,  # 对 voucher 不应产生限制
        applicable_venues=applicable_venues,
    )

    if applicable_venues:
        assert {v.id for v in filtered} == picked
    else:
        assert {v.id for v in filtered} == set(venue_ids)


def test_property_14_service_package_requires_region_match_and_whitelist():
    # 三个场所：分别归属不同地区
    venues = [
        VenueLite(
            id="v_city_ok",
            region=VenueRegion(country_code="COUNTRY:CN", province_code="PROVINCE:110000", city_code="CITY:110100"),
        ),
        VenueLite(
            id="v_city_bad",
            region=VenueRegion(country_code="COUNTRY:CN", province_code="PROVINCE:110000", city_code="CITY:999999"),
        ),
        VenueLite(
            id="v_province_ok",
            region=VenueRegion(country_code="COUNTRY:CN", province_code="PROVINCE:110000", city_code=None),
        ),
    ]

    # 允许 CITY:110100 与 PROVINCE:110000：
    # - province 级别应覆盖该省下所有城市场所
    filtered = filter_venues_by_entitlement(
        venues=venues,
        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
        applicable_regions=["CITY:110100", "PROVINCE:110000"],
        applicable_venues=["v_city_ok", "v_city_bad", "v_province_ok"],
    )
    assert {v.id for v in filtered} == {"v_city_ok", "v_city_bad", "v_province_ok"}

    # 若白名单仅包含 v_city_ok，则 province_ok 即使区域匹配也必须被过滤掉
    filtered2 = filter_venues_by_entitlement(
        venues=venues,
        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
        applicable_regions=["CITY:110100", "PROVINCE:110000"],
        applicable_venues=["v_city_ok"],
    )
    assert {v.id for v in filtered2} == {"v_city_ok"}

    # 若无 applicableRegions，则必须全部不可用
    filtered3 = filter_venues_by_entitlement(
        venues=venues,
        entitlement_type=EntitlementType.SERVICE_PACKAGE.value,
        applicable_regions=[],
        applicable_venues=None,
    )
    assert filtered3 == []

