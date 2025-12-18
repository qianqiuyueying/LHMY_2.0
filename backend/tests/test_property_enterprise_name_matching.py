"""属性测试：企业名称智能匹配（Property 9）与企业名规范化（Property 11）。

规格来源：
- specs/health-services-platform/design.md -> 企业名称智能匹配（匹配策略/排序/阈值/上限）
- specs/health-services-platform/design.md -> 企业信息持久化：企业名规范化唯一性
"""

from __future__ import annotations

import string

from hypothesis import given, strategies as st

from app.services.enterprise_matching import EnterpriseCandidate, normalize_enterprise_name, suggest_enterprises


@given(
    # v1 口径：企业名称主要由中文/英文/数字/空格构成；此处限定为 ASCII（避免 Unicode 特例导致 upper/lower 非对称）
    raw=st.text(alphabet=list(string.ascii_letters + string.digits + " "), min_size=1, max_size=30),
)
def test_property_11_enterprise_name_normalization_ignores_spaces_and_case(raw: str):
    # **Feature: health-services-platform, Property 11: 企业信息持久化**
    # 断言：去空格 + 统一大小写（lower）后，空格与大小写差异不影响规范化结果
    a = f"  {raw}  "
    b = "".join(list(raw)).upper()
    assert normalize_enterprise_name(a) == normalize_enterprise_name(b)


@given(
    name=st.text(min_size=1, max_size=20),
)
def test_property_9_exact_match_ranks_first(name: str):
    # **Feature: health-services-platform, Property 9: 企业名称智能匹配**
    # 构造一个企业库，其中包含与输入规范化后等价的企业名
    base = name
    normalized = normalize_enterprise_name(base)
    if not normalized:
        return

    enterprises = [
        EnterpriseCandidate(id="1", name="其他企业"),
        EnterpriseCandidate(id="2", name=base),
        EnterpriseCandidate(id="3", name=f"  {base}  "),
    ]

    suggestions = suggest_enterprises(keyword=base, enterprises=enterprises, limit=10)
    assert suggestions, "至少应返回一条匹配建议"
    # 规范化等价的精确匹配应排在最前（两条都算精确，按 name 二次排序）
    assert normalize_enterprise_name(suggestions[0].name) == normalized

