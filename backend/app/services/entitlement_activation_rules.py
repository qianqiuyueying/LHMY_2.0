"""权益激活规则（属性23：权益激活不可逆性）。

规格来源：
- specs/health-services-platform/design.md -> 属性 23：权益激活不可逆性
- specs/health-services-platform/tasks.md -> 阶段17-87.4

v1 最小落地口径：
- 使用 Entitlement.activator_id 作为“已激活”的不可逆标记：
  - 空串/仅空白：视为未激活
  - 非空：视为已激活（不可逆）
- 激活写入策略：
  - 若当前已激活（current_activator_id 非空），后续任何激活写入都不得覆盖
  - 若当前未激活，则写入本次 activator_id（要求非空）

说明：
- 该规则不引入新的对外 API 字段或端点，仅约束内部状态写入的不可逆性。
"""

from __future__ import annotations


def apply_entitlement_activation(*, current_activator_id: str, activator_id: str) -> str:
    """应用一次“激活”写入，返回新的 activator_id 值。"""

    cur = (current_activator_id or "").strip()
    if cur:
        return cur

    new = (activator_id or "").strip()
    if not new:
        # v1：激活者必须有值；调用方应保证
        raise ValueError("activator_id 不能为空")
    return new
