"""首次建库:把 data/sop/*.md 切块 + 嵌入,灌进 Chroma。

用法:
  python -m rag_agent.build_index            # 增量追加
  python -m rag_agent.build_index --rebuild  # 清空重建
"""
from __future__ import annotations

import sys

from rag_agent.config import rag_config
from rag_agent.rag.chunker import load_sop_docs
from rag_agent.rag.vectorstore import get_vectorstore


def build(rebuild: bool = False) -> int:
    vs = get_vectorstore()
    if rebuild:
        try:
            vs.delete_collection()
        except Exception:
            pass
        vs = get_vectorstore()
    docs = load_sop_docs(rag_config.sop_dir)
    # 稳定 id:label + 序号,避免重复嵌入
    ids = [f"{d.metadata['label']}__{i}" for i, d in enumerate(docs)]
    vs.add_documents(docs, ids=ids)
    return len(docs)


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv
    n = build(rebuild=rebuild)
    print(f"indexed {n} chunks into {rag_config.chroma_dir}")
