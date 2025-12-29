"""场所筛选规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> `GET /api/v1/venues`（regionLevel/regionCode、entitlementId 过滤）
- specs/health-services-platform/design.md -> 属性 14：权益使用场所过滤正确性
- specs/health-services-platform/tasks.md -> 阶段6-35.1/35.4

说明（v1 最小）：
- 当传入 entitlementId 时，认为“按某权益的适用范围过滤场所”，即：仅返回 eligible 的场所。
- eligibility 判断复用 `entitlement_scope_rules.is_entitlement_eligible_for_venue`。
- 地区筛选使用 `Venue.countryCode/provinceCode/cityCode` 三列，值口径为统一字符串编码（如 'CITY:110100'）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.entitlement_scope_rules import is_entitlement_eligible_for_venue


@dataclass(frozen=True)
class VenueRegion:
    country_code: str | None
    province_code: str | None
    city_code: str | None


@dataclass(frozen=True)
class VenueLite:
    id: str
    region: VenueRegion


def _normalize_region_code(*, region_level: str | None, region_code: str | None) -> tuple[str | None, str | None]:
    """将 query 的 regionLevel/regionCode 规范化为 (LEVEL, CODE_TEXT)。

    兼容两种输入：
    - regionCode 本身已包含 LEVEL 前缀（例如 'CITY:110100'）
    - regionCode 为纯 code（例如 '110100'），则拼接为 'CITY:110100'
    """

    if not region_level or not region_code:
        return None, None

    level = region_level.strip().upper()
    raw = region_code.strip()
    if not level or not raw:
        return None, None
    if level not in {"CITY", "PROVINCE", "COUNTRY"}:
        return None, None

    if ":" in raw:
        # 已是完整编码：例如 CITY:110100
        return level, raw
    return level, f"{level}:{raw}"


def matches_region_filter(*, venue: VenueLite, region_level: str | None, region_code: str | None) -> bool:
    """地区筛选（v1 最小）：按 regionLevel 对应的列精确匹配。"""

    level, normalized = _normalize_region_code(region_level=region_level, region_code=region_code)
    if not level or not normalized:
        return True

    if level == "COUNTRY":
        return bool(venue.region.country_code) and venue.region.country_code == normalized
    if level == "PROVINCE":
        return bool(venue.region.province_code) and venue.region.province_code == normalized
    if level == "CITY":
        return bool(venue.region.city_code) and venue.region.city_code == normalized
    return True


def filter_venues_by_entitlement(
    *,
    venues: list[VenueLite],
    entitlement_type: str,
    applicable_regions: list[str] | None,
    applicable_venues: list[str] | None,
) -> list[VenueLite]:
    """按权益适用范围过滤场所（属性14）。"""

    return [
        v
        for v in venues
        if is_entitlement_eligible_for_venue(
            entitlement_type=entitlement_type,
            applicable_regions=applicable_regions,
            applicable_venues=applicable_venues,
            venue_id=v.id,
            venue_country_code=v.region.country_code,
            venue_province_code=v.region.province_code,
            venue_city_code=v.region.city_code,
        )
    ]
