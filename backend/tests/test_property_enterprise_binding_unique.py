"""属性测试：企业绑定唯一性（属性10）。"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.models.enums import UserEnterpriseBindingStatus
from app.services.enterprise_binding_rules import can_submit_new_binding


@given(
    st.lists(
        st.sampled_from(
            [
                UserEnterpriseBindingStatus.PENDING,
                UserEnterpriseBindingStatus.APPROVED,
                UserEnterpriseBindingStatus.REJECTED,
            ]
        )
    )
)
def test_property_10_enterprise_binding_uniqueness(statuses: list[UserEnterpriseBindingStatus]):
    """属性10：存在 APPROVED 必须拒绝新的绑定申请。"""

    allowed = can_submit_new_binding(statuses)

    if UserEnterpriseBindingStatus.APPROVED in statuses:
        assert allowed is False


def test_property_10_rejected_allows_resubmit():
    """属性10：仅 REJECTED 允许再次提交。"""

    assert can_submit_new_binding([UserEnterpriseBindingStatus.REJECTED]) is True
    assert can_submit_new_binding([UserEnterpriseBindingStatus.REJECTED, UserEnterpriseBindingStatus.REJECTED]) is True
