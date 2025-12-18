"""账号合并：数据迁移裁决（v1 最小可执行）。

规格来源：
- specs/health-services-platform/design.md -> 跨端身份联通口径：数据迁移表清单与“手机号账户为主”
- specs/health-services-platform/tasks.md -> 阶段3-16.3/16.4

说明：
- 本模块只实现“迁移哪些字段”的纯规则（可属性测试）。
- 真实数据库迁移在 API 层使用 SQL update 执行（见 mini_program_auth.py）。
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class AccountMergeDataset:
    entitlement_owner_ids: list[str]
    service_package_instance_owner_ids: list[str]
    order_user_ids: list[str]
    booking_user_ids: list[str]
    after_sale_user_ids: list[str]
    redemption_user_ids: list[str]
    transfer_from_owner_ids: list[str]
    transfer_to_owner_ids: list[str]


def apply_account_merge(*, dataset: AccountMergeDataset, source_user_id: str, target_user_id: str) -> AccountMergeDataset:
    """将 source_user_id 的裁决字段迁移到 target_user_id。"""

    def _map(ids: list[str]) -> list[str]:
        return [target_user_id if x == source_user_id else x for x in ids]

    return replace(
        dataset,
        entitlement_owner_ids=_map(dataset.entitlement_owner_ids),
        service_package_instance_owner_ids=_map(dataset.service_package_instance_owner_ids),
        order_user_ids=_map(dataset.order_user_ids),
        booking_user_ids=_map(dataset.booking_user_ids),
        after_sale_user_ids=_map(dataset.after_sale_user_ids),
        redemption_user_ids=_map(dataset.redemption_user_ids),
        transfer_from_owner_ids=_map(dataset.transfer_from_owner_ids),
        transfer_to_owner_ids=_map(dataset.transfer_to_owner_ids),
    )

