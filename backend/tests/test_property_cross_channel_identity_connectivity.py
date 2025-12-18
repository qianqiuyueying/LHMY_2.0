"""属性测试：跨端身份联通（含合并后的 userId 联通）。

对应：
- specs/health-services-platform/tasks.md -> 阶段3-16.4
- specs/health-services-platform/design.md -> 跨端身份联通口径：数据迁移表清单

说明：
- 该属性测试验证“合并迁移规则”本身，不依赖真实支付/权益生成流程。
"""

from __future__ import annotations

from hypothesis import given, strategies as st

from app.services.account_merge_rules import AccountMergeDataset, apply_account_merge


@given(
    source=st.text(min_size=1, max_size=8),
    target=st.text(min_size=1, max_size=8),
    entitlement_owner_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    service_package_instance_owner_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    order_user_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    booking_user_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    after_sale_user_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    redemption_user_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    transfer_from_owner_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
    transfer_to_owner_ids=st.lists(st.text(min_size=0, max_size=8), max_size=30),
)
def test_property_7_cross_channel_identity_connectivity(
    source: str,
    target: str,
    entitlement_owner_ids: list[str],
    service_package_instance_owner_ids: list[str],
    order_user_ids: list[str],
    booking_user_ids: list[str],
    after_sale_user_ids: list[str],
    redemption_user_ids: list[str],
    transfer_from_owner_ids: list[str],
    transfer_to_owner_ids: list[str],
):
    # **Feature: health-services-platform, Property 7: 服务包权益生成可见性（验证合并后同一 userId 联通）**
    # 约束：source/target 不同，否则迁移无意义
    if source == target:
        return

    dataset = AccountMergeDataset(
        entitlement_owner_ids=entitlement_owner_ids,
        service_package_instance_owner_ids=service_package_instance_owner_ids,
        order_user_ids=order_user_ids,
        booking_user_ids=booking_user_ids,
        after_sale_user_ids=after_sale_user_ids,
        redemption_user_ids=redemption_user_ids,
        transfer_from_owner_ids=transfer_from_owner_ids,
        transfer_to_owner_ids=transfer_to_owner_ids,
    )

    merged = apply_account_merge(dataset=dataset, source_user_id=source, target_user_id=target)

    # 断言：所有需要迁移的裁决字段中，不再出现 source
    assert source not in merged.entitlement_owner_ids
    assert source not in merged.service_package_instance_owner_ids
    assert source not in merged.order_user_ids
    assert source not in merged.booking_user_ids
    assert source not in merged.after_sale_user_ids
    assert source not in merged.redemption_user_ids
    assert source not in merged.transfer_from_owner_ids
    assert source not in merged.transfer_to_owner_ids

