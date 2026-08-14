"""rag_agent FastAPI 路由,挂在 /agent(由 app/main.py include)。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.db import get_record

router = APIRouter(tags=["rag-agent"])


@router.get("/", response_class=HTMLResponse)
def workspace():
    """处置工作台(独立前端页,零侵入 ShopInspect static/)。"""
    return (Path(__file__).parent / "ui.html").read_text(encoding="utf-8")


@router.get("/dispose")
def dispose_record(record_id: int, use_agent: bool = True):
    """读检测记录的 top_label,返回处置方案。

    - use_agent=True(默认):Agent 编排(查SOP + 查历史 + 多步方案 + 高危标注)。
    - use_agent=False:直接 RAG 检索(纯 SOP + 来源)。
    """
    rec = get_record(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"record {record_id} not found")
    top_label = rec.get("top_label") or "unknown"
    if use_agent:
        from rag_agent.agent.graph import dispose_with_agent

        result = dispose_with_agent(top_label, record_id)
    else:
        from rag_agent.rag.retriever import dispose

        result = dispose(top_label)
    return {
        "record_id": record_id,
        "top_label": top_label,
        "status": rec.get("status"),
        **result,
    }


class ConfirmRequest(BaseModel):
    record_id: int
    action: str
    approved: bool = True
    operator: str = "unknown"


@router.post("/dispose/confirm")
def confirm_action(req: ConfirmRequest):
    """高危处置动作人工确认(HITL):Agent 标注的高危项由人来批准。"""
    from rag_agent.hitl import record_confirmation

    entry = record_confirmation(req.record_id, req.action, req.approved, req.operator)
    return {"confirmed": True, **entry}


@router.get("/health")
def health():
    return {"ok": True, "module": "rag_agent"}
