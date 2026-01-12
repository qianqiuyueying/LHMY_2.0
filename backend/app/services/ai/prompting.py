"""Prompt 拼接（v2）。"""

from __future__ import annotations

from app.services.ai.risk import build_health_disclaimer


def build_system_prompt(*, prompt_template: str, constraints: dict) -> str:
    """构造 system prompt（provider 无关）。

    规则：
    - prompt_template 为运营配置的业务语义
    - safe_mode 时强制注入“非医疗诊断”边界声明（避免运营漏写导致风险）
    """

    base = (prompt_template or "").strip()
    safe_mode = bool((constraints or {}).get("safe_mode"))
    forbid_diagnosis = bool((constraints or {}).get("forbid_medical_diagnosis"))

    parts: list[str] = []
    if base:
        parts.append(base)
    if safe_mode or forbid_diagnosis:
        parts.append("你是健康领域知识助手，只做科普与一般性建议，不做医疗诊断、不提供处方与用药剂量。")
        parts.append(build_health_disclaimer())
    return "\n\n".join([p for p in parts if p.strip()]).strip()


def build_single_turn_prompt(*, prompt_template: str, user_message: str, constraints: dict) -> str:
    """DashScope 应用模式等“单 prompt”接口的 prompt 拼接。"""

    sys = build_system_prompt(prompt_template=prompt_template, constraints=constraints)
    q = (user_message or "").strip()
    if sys:
        return f"{sys}\n\n用户问题：{q}"
    return q

