"""AI 风控与边界（v2）。

规格来源：
- specs/health-services-platform/ai-gateway-v2.md -> 风控与边界（必须实现）

说明：
- v2 最小：对“诊断/处方/用药剂量”等明显医疗诊断诉求做拒答，不调用第三方 AI。
- 该逻辑必须 provider 无关，避免因 provider 限制反向污染 Strategy。
"""

from __future__ import annotations

import re


_DIAGNOSIS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(诊断|确诊|是不是得了|是否得了|是不是患了|是否患了)"),
    re.compile(r"(开药|处方|配药|用药|吃什么药|用什么药|药量|剂量|多久吃一次|一天吃几次)"),
    re.compile(r"(怎么治|如何治疗|治疗方案|手术|需要手术吗|要不要住院)"),
    re.compile(r"(检查报告|化验单|CT|核磁|MRI|B超|血常规|指标异常)"),
]


def is_medical_diagnosis_request(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    for p in _DIAGNOSIS_PATTERNS:
        if p.search(s):
            return True
    return False


def build_health_disclaimer() -> str:
    # 注意：这是“非医疗声明”，不是 UI 免责声明（UI 仍可保留更短版本）
    return "提示：以下内容仅用于健康科普与一般性建议，不构成医疗诊断或治疗方案。如有不适请及时就医。"


def refusal_for_diagnosis() -> str:
    return (
        "我可以做健康科普与一般建议，但不能提供医疗诊断、处方或具体用药剂量建议。"
        "如果你愿意，可以描述你的年龄段、主要症状持续时间、既往病史与当前已做检查项目，我可以帮你整理就医时的提问清单与可能需要关注的风险点。"
    )

