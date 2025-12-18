"""权益适用范围规则（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 属性 13：权益类型和适用范围匹配
- specs/health-services-platform/design.md -> 区域编码口径（CITY/PROVINCE/COUNTRY）
- specs/health-services-platform/tasks.md -> 阶段5-33

v1 最小口径：
- 基建联防权益（entitlementType=VOUCHER）：全平台通用（不做区域限制）
- 健行天下权益（entitlementType=SERVICE_PACKAGE）：必须匹配 applicableRegions（区域限制）
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import EntitlementType


@dataclass(frozen=True)
class RegionScope:
    level: str  # CITY|PROVINCE|COUNTRY
    code: str


def parse_region_scope(value: str) -> RegionScope | None:
    if not value or ":" not in value:
        return None
    level, code = value.split(":", 1)
    level = level.strip().upper()
    code = code.strip()
    if level not in {"CITY", "PROVINCE", "COUNTRY"}:
        return None
    if not code:
        return None
    return RegionScope(level=level, code=code)


def venue_region_matches_scope(
    *,
    scope: str,
    venue_country_code: str | None,
    venue_province_code: str | None,
    venue_city_code: str | None,
) -> bool:
    parsed = parse_region_scope(scope)
    if parsed is None:
        return False
    if parsed.level == "COUNTRY":
        return bool(venue_country_code) and venue_country_code == scope
    if parsed.level == "PROVINCE":
        return bool(venue_province_code) and venue_province_code == scope
    if parsed.level == "CITY":
        return bool(venue_city_code) and venue_city_code == scope
    return False


def is_entitlement_eligible_for_venue(
    *,
    entitlement_type: str,
    applicable_regions: list[str] | None,
    applicable_venues: list[str] | None,
    venue_id: str,
    venue_country_code: str | None,
    venue_province_code: str | None,
    venue_city_code: str | None,
) -> bool:
    """判断某权益是否可在指定场所使用（仅适用范围，不含次数/状态/预约等）。"""

    # 场所白名单：若配置则必须命中
    if applicable_venues is not None and len(applicable_venues) > 0 and venue_id not in applicable_venues:
        return False

    # 基建联防：全平台通用
    if entitlement_type == EntitlementType.VOUCHER.value:
        return True

    # 健行天下：区域限制
    if entitlement_type == EntitlementType.SERVICE_PACKAGE.value:
        if not applicable_regions:
            return False
        return any(
            venue_region_matches_scope(
                scope=x,
                venue_country_code=venue_country_code,
                venue_province_code=venue_province_code,
                venue_city_code=venue_city_code,
            )
            for x in applicable_regions
        )

    # 未知类型：保守拒绝
    return False

