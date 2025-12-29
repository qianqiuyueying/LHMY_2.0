"""属性测试：权益激活不可逆性（属性23）。

规格来源：
- specs/health-services-platform/design.md -> 属性 23：权益激活不可逆性
- specs/health-services-platform/tasks.md -> 阶段17-87.4

v1 最小断言（实现口径见 app/services/entitlement_activation_rules.py）：
- 一旦 activator_id 被写入为非空值，后续任何“激活写入”不得将其恢复为空或覆盖为其他值
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from app.services.entitlement_activation_rules import apply_entitlement_activation


@given(
    # v1：激活者通常为主体ID（uuid-like 文本）；避免生成仅空白字符导致无效输入
    first=st.from_regex(r"[A-Za-z0-9_-]{1,36}", fullmatch=True),
    second=st.from_regex(r"[A-Za-z0-9_-]{1,36}", fullmatch=True),
)
def test_property_23_activation_is_irreversible(first: str, second: str):
    # 第一次激活：从空 -> 写入 first
    a1 = apply_entitlement_activation(current_activator_id="", activator_id=first)
    assert a1.strip() == first.strip()
    assert a1.strip() != ""

    # 第二次激活：不得覆盖为 second
    a2 = apply_entitlement_activation(current_activator_id=a1, activator_id=second)
    assert a2 == a1


def test_property_23_reject_empty_activator_id():
    with pytest.raises(ValueError):
        apply_entitlement_activation(current_activator_id="", activator_id="  ")
