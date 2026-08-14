"""rag_agent 独立配置:从 .env 读取,不依赖也不修改 app/config.py。

理由:app/config.py 用 @dataclass + yaml 白名单过滤,加字段须改 dataclass;
rag_agent 走自己的 dotenv,完全自包含,只在 main.py 加一行接入。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")


@dataclass(frozen=True)
class RagConfig:
    # SiliconFlow(OpenAI 兼容)
    api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    chat_model: str = os.getenv("CHAT_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")
    # 检索相似度阈值:1/(1+L2距离),低于此的 chunk 丢弃
    min_score: float = float(os.getenv("RAG_MIN_SCORE", "0.3"))
    # 路径
    base_dir: Path = _BASE_DIR
    sop_dir: Path = _BASE_DIR / "data" / "sop"
    chroma_dir: Path = _BASE_DIR / "data" / "chroma"
    collection: str = "defect_sop"

    def assert_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "SILICONFLOW_API_KEY 未设置,请检查 rag_agent/.env"
            )


rag_config = RagConfig()
