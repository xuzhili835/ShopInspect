"""Chroma 持久化向量库(本地落盘)。"""
from __future__ import annotations

from langchain_chroma import Chroma

from rag_agent.config import rag_config
from rag_agent.rag.embedder import get_embedder


def get_vectorstore() -> Chroma:
    """获取/创建持久化 Chroma(collection 不存在则自动建)。"""
    return Chroma(
        collection_name=rag_config.collection,
        embedding_function=get_embedder(),
        persist_directory=str(rag_config.chroma_dir),
    )
