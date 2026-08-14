"""rag_agent FastAPI 路由,挂在 /agent(由 app/main.py include)。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import get_record
from rag_agent.rag.retriever import dispose

router = APIRouter(tags=["rag-agent"])


@router.get("/dispose")
def dispose_record(record_id: int):
    """读 ShopInspect 检测记录的 top_label,返回该缺陷的处置 SOP + 来源。

    同进程 `import app.db`(不走网络),单端口 :8787/agent/dispose。
    """
    rec = get_record(record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"record {record_id} not found")
    top_label = rec.get("top_label") or "unknown"
    result = dispose(top_label)
    return {
        "record_id": record_id,
        "top_label": top_label,
        "status": rec.get("status"),
        **result,
    }


@router.get("/health")
def health():
    return {"ok": True, "module": "rag_agent"}
