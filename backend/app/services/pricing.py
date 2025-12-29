"""价格裁决（v1）。

规格来源：
- specs/health-services-platform/design.md -> 属性12：价格优先级计算一致性
- specs/health-services-platform/tasks.md -> 阶段2-6.5

口径（已确认）：
- 活动状态：当前阶段 activity 非空即视为活动生效（不引入时间范围）
- 可命中集合：original 永远可命中；member/employee 需身份命中；activity 只要非空即可命中
- 最终价：取“可命中集合”中的最低价；若最低价有并列，则按 activity > member > employee > original 选择来源类型
"""

from __future__ import annotations

from typing import Any, Iterable, Literal, Tuple


PriceType = Literal["activity", "member", "employee", "original"]


def _is_number(v: object) -> bool:
    try:
        return v is not None and isinstance(v, (int, float)) and not (v != v)  # noqa: PLR0124
    except Exception:
        return False


def resolve_price(price: dict[str, Any], *, identities: Iterable[str] | None = None) -> Tuple[float, PriceType]:
    """按“可命中集合取最低价”裁决最终价格，并返回来源类型。

    约定：price 结构形如：
    { original: number, employee?: number, member?: number, activity?: number }

    注意：
    - v1 不处理货币精度/折扣叠加等扩展口径
    - 活动生效口径：activity 非空即视为生效（不引入时间范围）
    """

    ids = set(str(x) for x in (identities or []) if str(x).strip())

    original = price.get("original")
    if not _is_number(original):
        raise ValueError("price.original 不能为空")

    candidates: list[tuple[PriceType, float]] = [("original", float(original))]

    activity = price.get("activity")
    if _is_number(activity):
        candidates.append(("activity", float(activity)))

    member = price.get("member")
    if "MEMBER" in ids and _is_number(member):
        candidates.append(("member", float(member)))

    employee = price.get("employee")
    if "EMPLOYEE" in ids and _is_number(employee):
        candidates.append(("employee", float(employee)))

    # 取最低价；并列按 activity > member > employee > original
    min_price = min(p for _t, p in candidates)
    tied = [t for t, p in candidates if p == min_price]
    priority: list[PriceType] = ["activity", "member", "employee", "original"]
    for t in priority:
        if t in tied:
            return (min_price, t)

    return (min_price, "original")
