"""属性测试：权益生成双形态完整性（属性21）与归属者唯一性（属性22）。"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.entitlement_rules import EntitlementShape, validate_entitlement_shape


@given(
    st.text(min_size=1),
    st.text(min_size=1),
    st.text(min_size=1),
)
def test_property_21_22_entitlement_shape(owner_id: str, qr_code: str, voucher_code: str):
    validate_entitlement_shape(EntitlementShape(owner_id=owner_id, qr_code=qr_code, voucher_code=voucher_code))


def test_property_21_22_reject_empty_fields():
    try:
        validate_entitlement_shape(EntitlementShape(owner_id="", qr_code="x", voucher_code="y"))
        assert False
    except ValueError:
        pass

    try:
        validate_entitlement_shape(EntitlementShape(owner_id="u", qr_code="", voucher_code="y"))
        assert False
    except ValueError:
        pass

    try:
        validate_entitlement_shape(EntitlementShape(owner_id="u", qr_code="x", voucher_code=""))
        assert False
    except ValueError:
        pass
