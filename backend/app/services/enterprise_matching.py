"""企业名称智能匹配（Property 9）与规范化（Property 11）。

规格来源：
- specs/health-services-platform/design.md -> 企业名称智能匹配（Property 9，v1 最小可执行）
- specs/health-services-platform/design.md -> 企业信息持久化（Property 11，v1 最小可执行）
"""

from __future__ import annotations

from dataclasses import dataclass


def normalize_enterprise_name(name: str) -> str:
    """企业名规范化（v1）：去除空格、统一大小写。"""

    if not isinstance(name, str):
        return ""
    return "".join(name.split()).lower()


def levenshtein_distance(a: str, b: str) -> int:
    """编辑距离（Levenshtein）。"""

    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # DP：O(len(a)*len(b))
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


@dataclass(frozen=True)
class EnterpriseCandidate:
    id: str
    name: str
    city_code: str | None = None


@dataclass(frozen=True)
class EnterpriseSuggestion:
    id: str
    name: str
    city_code: str | None


def suggest_enterprises(
    *, keyword: str, enterprises: list[EnterpriseCandidate], limit: int = 10
) -> list[EnterpriseSuggestion]:
    """按规格返回匹配建议（最多 10 条）。"""

    key = normalize_enterprise_name(keyword)
    if not key:
        return []

    ranked: list[tuple[int, int, EnterpriseCandidate]] = []
    for e in enterprises:
        n = normalize_enterprise_name(e.name)
        if not n:
            continue

        # 1. 精确匹配
        if n == key:
            ranked.append((0, 0, e))
            continue
        # 2. 前缀匹配
        if n.startswith(key):
            ranked.append((1, 0, e))
            continue
        # 3. 包含匹配
        if key in n:
            ranked.append((2, 0, e))
            continue
        # 4. 相似度匹配（编辑距离<=2）
        dist = levenshtein_distance(key, n)
        if dist <= 2:
            ranked.append((3, dist, e))

    ranked.sort(key=lambda x: (x[0], x[1], x[2].name))
    return [EnterpriseSuggestion(id=e.id, name=e.name, city_code=e.city_code) for _, __, e in ranked[: max(0, limit)]]
