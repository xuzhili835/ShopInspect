"""HITL:高危处置动作识别与人工确认。

高危动作(换件/停机/报废等)不能由 Agent 直接拍板,需人工确认后再执行。
本模块负责:从 Agent 方案文本识别高危项 + 记录人工确认。
"""
from __future__ import annotations

# 高危关键词:方案中出现即视为需人工确认
HIGH_RISK_KEYWORDS = [
    "换件",
    "更换",
    "停机",
    "停线",
    "报废",
    "替换",
    "停产",
    "补焊",
]

# 简单内存确认记录(demo 用;生产应落库持久化)
_confirmations: dict[str, dict] = {}


def extract_high_risk_actions(plan_text: str) -> list[str]:
    """从处置方案文本中识别高危动作关键词(去重保序)。"""
    found: list[str] = []
    for kw in HIGH_RISK_KEYWORDS:
        if kw in plan_text and kw not in found:
            found.append(kw)
    return found


def needs_confirmation(plan_text: str) -> bool:
    return bool(extract_high_risk_actions(plan_text))


def record_confirmation(
    record_id: int, action: str, approved: bool, operator: str
) -> dict:
    """记录一次人工确认结果。"""
    key = f"{record_id}:{action}"
    entry = {
        "record_id": record_id,
        "action": action,
        "approved": approved,
        "operator": operator,
    }
    _confirmations[key] = entry
    return entry
