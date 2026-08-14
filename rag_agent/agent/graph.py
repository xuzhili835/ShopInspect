"""LangGraph ReAct Agent:编排「查 SOP + 查历史」→ 给多步处置方案。

用 langgraph.prebuilt.create_react_agent 构建 Function Calling 循环,
Qwen3-30B-A3B-Instruct 做决策,工具为 query_sop / query_history。
高危动作(换件/停机等)在方案中标注,由 HITL 模块识别 + 端点确认。
"""
from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from rag_agent.agent.tools import query_history, query_sop
from rag_agent.config import rag_config
from rag_agent.hitl import extract_high_risk_actions

SYSTEM_PROMPT = """你是工业产线的缺陷处置专家 Agent。给定检出的缺陷类别,按以下流程工作:
1. 调用 query_sop 查询该缺陷的标准维修流程(SOP)。
2. 调用 query_history 查询该缺陷的历史出现情况,判断是否频发。
3. 综合两者,给出多步处置方案:症状判断 → 严重度评估 → 处置步骤 → 复检标准。

规则:
- 涉及"换件/停机/报废/停线/补焊"等高危动作时,在该步骤后明确标注【需人工确认】。
- 用中文回答,条理清晰,分步骤编号。
- 基于查询到的 SOP 和历史作答,不要编造规程之外的步骤。"""

_agent: Any = None


def get_agent() -> Any:
    """惰性构建并缓存 ReAct Agent。"""
    global _agent
    if _agent is None:
        llm = ChatOpenAI(
            model=rag_config.chat_model,
            api_key=rag_config.api_key,
            base_url=rag_config.base_url,
            temperature=0.3,
        )
        _agent = create_react_agent(
            llm, tools=[query_sop, query_history], prompt=SYSTEM_PROMPT
        )
    return _agent


def dispose_with_agent(defect_label: str, record_id: int | None = None) -> dict:
    """Agent 编排处置:多步方案 + 高危待确认项。

    Returns: {found, dispose, high_risk_actions, needs_confirmation}
    """
    agent = get_agent()
    rid = f"(检测记录 #{record_id}) " if record_id is not None else ""
    user_msg = (
        f"本次检测{rid}检出缺陷类别:{defect_label}。"
        f"请查询其 SOP 和历史出现情况,给出完整处置方案。"
    )
    result = agent.invoke({"messages": [("user", user_msg)]})
    plan = result["messages"][-1].content
    high_risk = extract_high_risk_actions(plan)
    return {
        "found": True,
        "dispose": plan,
        "high_risk_actions": high_risk,
        "needs_confirmation": bool(high_risk),
    }
