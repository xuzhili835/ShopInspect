"""bge-m3 嵌入,走 SiliconFlow(OpenAI 兼容)。"""
from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from rag_agent.config import rag_config


def get_embedder() -> OpenAIEmbeddings:
    rag_config.assert_key()
    return OpenAIEmbeddings(
        model=rag_config.embedding_model,
        api_key=rag_config.api_key,
        base_url=rag_config.base_url,
        # SOP 文本很短,禁用 tiktoken 分块校验,避免额外依赖
        check_embedding_ctx_length=False,
    )
