"""检索:metadata filter(按缺陷类 label) + 相似度阈值 + 无命中拒答 + 来源引用。"""
from __future__ import annotations

from rag_agent.config import rag_config
from rag_agent.rag.vectorstore import get_vectorstore


def _to_similarity(l2_distance: float) -> float:
    """Chroma 默认返回 L2 距离(越小越相似),转成 0~1 相似度(越大越相似)。"""
    return 1.0 / (1.0 + max(0.0, l2_distance))


def retrieve(top_label: str, k: int = 4) -> list[dict]:
    """按缺陷类 label 过滤检索 SOP,丢弃低于阈值的结果,返回带来源的命中。"""
    vs = get_vectorstore()
    query = f"{top_label} 缺陷 处置 维修 步骤 严重度 复检"
    raw = vs.similarity_search_with_score(query, k=k, filter={"label": top_label})
    hits: list[dict] = []
    for doc, score in raw:
        sim = _to_similarity(float(score))
        if sim >= rag_config.min_score:
            hits.append(
                {
                    "content": doc.page_content,
                    "file": doc.metadata.get("file", ""),
                    "section": doc.metadata.get("section", ""),
                    "score": round(sim, 3),
                }
            )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits


def dispose(top_label: str) -> dict:
    """检索并组装处置结果:命中返回处置文本 + 来源;无命中拒答。"""
    hits = retrieve(top_label)
    if not hits:
        return {
            "found": False,
            "dispose": f"未找到 {top_label} 类型的处置 SOP,请人工处理。",
            "sources": [],
        }
    text = "\n\n".join(h["content"] for h in hits)
    sources = [
        {"file": h["file"], "section": h["section"], "score": h["score"]}
        for h in hits
    ]
    return {"found": True, "dispose": text, "sources": sources}
