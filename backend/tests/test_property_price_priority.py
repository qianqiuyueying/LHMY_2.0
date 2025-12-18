"""属性测试：价格优先级计算一致性（属性12）。"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.pricing import resolve_price


def _manual(price: dict) -> float:
    for key in ("activity", "member", "employee", "original"):
        v = price.get(key)
        if v is None:
            continue
        return float(v)
    raise ValueError


@given(
    st.fixed_dictionaries(
        {
            # original 必须存在
            "original": st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False),
            "employee": st.one_of(st.none(), st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False)),
            "member": st.one_of(st.none(), st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False)),
            "activity": st.one_of(st.none(), st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False)),
        }
    )
)
def test_property_12_price_priority_consistency(price: dict):
    assert resolve_price(price) == _manual(price)
