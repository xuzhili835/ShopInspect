"""SOP markdown 切块:按标题层级切,带来源 metadata。"""
from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter

# 按一级/二级标题切块,保留 section 信息
_HEADERS = [("#", "section"), ("##", "subsection")]


def load_sop_docs(sop_dir: Path) -> list[Document]:
    """读取 sop_dir/*.md,按 markdown 标题切块;文件名即缺陷类 label。"""
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS)
    docs: list[Document] = []
    for md in sorted(sop_dir.glob("*.md")):
        label = md.stem  # 文件名 = 缺陷类(与模型类名对齐)
        chunks = splitter.split_text(md.read_text(encoding="utf-8"))
        for c in chunks:
            c.metadata["label"] = label
            c.metadata["file"] = md.name
            docs.append(c)
    return docs
