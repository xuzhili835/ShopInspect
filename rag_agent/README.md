# rag_agent — ShopInspect 缺陷处置 RAG + Agent

ShopInspect 的缺陷处置模块。检测出缺陷(alert)→ RAG 查维修 SOP → Agent 给处置步骤 → 高危人工确认。

## 接入方式(单进程单端口)
- 代码全在本目录;`app/main.py` 加一行 `app.include_router(router, prefix="/agent")` 挂载。
- 同进程 `from app.db import get_record` 读检测记录(不走网络)。
- 配置独立:`.env`(SiliconFlow key 等),不碰 `app/config.py`。

## 端点
- `GET /agent/dispose?record_id=xxx` — 读该记录 `top_label` → 检索缺陷 SOP → 返回处置文本 + 来源。

## 用法
```bash
# 1. 建库(首次):把 data/sop/*.md 灌进 Chroma
python -m rag_agent.build_index
# 2. 随 ShopInspect 一起起(python scripts/run_api.py),访问 :8787/agent/dispose
```

## 结构
```
rag_agent/
  config.py        # 独立配置(.env)
  rag/             # chunker + embedder + vectorstore + retriever
  agent/           # 阶段2:Function Calling + LangGraph
  hitl/            # 阶段2:高危人工确认
  api.py           # /agent 路由
  build_index.py   # 建库脚本
  data/sop/        # 6 类缺陷 SOP 种子(对齐 NEU-DET 类名)
  data/chroma/     # 向量库持久化(gitignore)
```

类名(英文 snake_case,与缺陷模型一致):
`crazing / inclusion / patches / pitted_surface / rolled-in_scale / scratches`

## 实际成果(已验证)

- **缺陷模型**:NEU-DET 6 类,**mAP50=0.817**,CPU 推理 27.6ms/张(`models/def_best.pt`)
- **RAG**:24 chunks 建库(Chroma),bge-m3 via SiliconFlow,score_threshold + 来源引用 + 无命中拒答
- **Agent**:LangGraph ReAct(`create_react_agent`),工具 query_sop + query_history,12-18s 出多步方案
- **HITL**:识别换件/停机/报废/补焊,`POST /agent/dispose/confirm` 批准/拒绝
- **端到端闭环**(已验证):上传缺陷图 → 检出 → Agent 方案(主动查历史判断频发) → 高危确认 → 工作台可视化

端点:
- `GET /agent/dispose?record_id=X&use_agent=true` — Agent 编排处置(use_agent=false 走纯 RAG)
- `POST /agent/dispose/confirm` — 高危动作人工确认
- `GET /agent/` — 处置工作台(独立前端页,零侵入 static/)
