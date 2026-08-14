# ShopInspect 融合方案 v3(全 Python,单进程)

> v1(Java 业务层 `backend-java/`)已**废弃删除**。v2 双端口(`:8787` + `:8081` REST)已**改为单进程单端口**。本版**全 Python**,和周靖统一栈。
> 配合 `HANDOFF_PROMPT.md`(交接提示词)一起用:本文档讲**为什么/怎么设计**,交接文档讲**做什么**。
> 更新:2026-08-14

---

## 一、合作分工(先把归属讲清,简历不撞)

| 模块 | 归属 | 技术栈 | 简历谁讲 |
|---|---|---|---|
| 视觉检测工程闭环(FastAPI + SQLite + 看板 + 摄像头)+ 通用检测 | **周靖**(已完成 V1.3) | Python / Ultralytics / FastAPI / SQLite / 原生 JS | 周靖 |
| **缺陷模型训练** + **缺陷处置 RAG + Agent + HITL**(新增) | **何承恩(你)** | Ultralytics 训练 / bge-m3 / Qwen3 / LangChain + LangGraph / Function Calling | 你 |

一句话:**ShopInspect 是和周靖合作的工业质检项目,周靖做检测工程闭环,我做缺陷模型训练 + 缺陷处置的 RAG + Agent**。

> 分工变更记录:缺陷模型原计划由周靖训(V2),现改由**何承恩自己训**。两人都碰视觉但侧重不同——周靖做工程闭环,何承恩做缺陷模型 + 处置,简历不打架。

---

## 二、架构(全 Python,单进程单端口)

```
┌─────────────────────────────────────────────────────────────┐
│ ShopInspect :8787   一个 FastAPI 进程   python run_api.py   │
│                                                              │
│  app/ (周靖)                     rag_agent/ (你)             │
│   YOLO(你的缺陷模型 def_best)    rag/    切块+嵌入+检索+来源  │
│   → SQLite records              agent/  Function Calling    │
│   → 看板                         hitl/   高危人工确认        │
│   (status=alert 即告警)         api.py  /agent/dispose       │
│         │                           ▲                        │
│         └──── 同进程 import app.db ──┘  读 record.top_label  │
│                                                              │
│   入口: app/main.py 加一行 app.include_router(rag_router)   │
└─────────────────────────────────────────────────────────────┘
```

**接入方式(单端口)**:
- rag_agent 的**代码全在 `rag_agent/` 目录**;唯一碰 `app/` 的地方是 `app/main.py` **加一行** `app.include_router(rag_router, prefix="/agent")`。
- 一个进程、一个端口 `:8787`、一条命令起。
- 读记录走**同进程 `from app.db import get_record`**(不走网络、不调 REST),少一个故障点。
- langchain/chroma 等依赖装进 ShopInspect **共用 `.venv`**。

> 接入点这一行属于"和周靖说一声"级别,不算改他的业务代码;PR review 时能看到。

---

## 三、ShopInspect 接口契约(rag_agent 消费)

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/records`(筛 source/label/work_order/batch_id) | 拉历史 / 告警 |
| GET | `/records/{id}` | 详情(含 detections 框) |
| GET | `/stats` | 汇总(by_label / alert_records) |
| GET | `/health` | 探活 |

**rag_agent 实际读法**:同进程直接 `from app.db import get_record`(比 REST 快、无网络)。HTTP 接口作为可选/调试通道保留。

**关键字段**:`status`(alert=检出 / clear=无)、`top_label`、`labels`({类:计数})、`detections[]`、`work_order`/`batch_id`、`source`。
**alert 语义**:V1 是"检出任何物体"(通用 COCO 权重);V2 切了**你的缺陷模型**后才是真缺陷告警。rag_agent 消费 alert 即可。

---

## 四、rag_agent/ 模块设计

```
rag_agent/
  __init__.py
  rag/         # chunker(切块)+ embedder(bge-m3)+ vectorstore(Chroma)+ retriever(min-score+来源)
  agent/       # 处置编排:Function Calling(查SOP/查历史/给步骤),Qwen3,LangGraph
  hitl/        # 高危操作人工确认(停机/换件)
  api.py       # FastAPI 路由,挂 main.py 单端口 :8787/agent
  data/sop/    # 缺陷维修 SOP 语料(种子:划痕/裂纹/脏污)
  README.md
```

**技术选型**(用框架不手写):
- 全 Python,和周靖统一栈;
- **RAG / Agent 用 LangChain** + **LangGraph**(Agent 编排 / HITL);
- 模型:**bge-m3 嵌入 + Qwen3-30B 对话**,都走 **SiliconFlow**(OpenAI 兼容),LangChain `ChatOpenAI`/`OpenAIEmbeddings`(改 base_url)接入;
- 向量库:**Chroma**(本地持久化);
- 慧医云是手搓(懂底层),本项目用 LangChain 工程化——简历互补。

> 嵌入走 API 的取舍:SOP 语料会过 SiliconFlow,确认 SOP 不涉密即可;若涉密,改本地 `HuggingFaceEmbeddings`,上层代码不动。

**你仍要做的(框架不替代)**:
- scope 隔离 → LangChain `metadata` filter(按缺陷类);
- 防幻觉 → retriever `score_threshold` + 无命中拒答 + 来源引用;
- 增量 → `VectorStore.add/delete_documents`;
- SOP 语料、prompt、业务编排、HITL(LangGraph)。

---

## 五、缺陷模型训练与交付(何承恩)

- **训练**:何承恩自备缺陷图片 + 标注,用 Ultralytics 训练,产物 `def_best.pt`。
- **交付给周靖**:走 **GitHub Release**(tag=`model-defect-vN`,附件 `.pt`,release notes 写**类名清单** + `imgsz` + ultralytics 版本 + 训练指标)。**不进 git 提交**(`*.pt` 已 gitignore)。
- **周靖接入**:改 `config.yaml: model_path → models/def_best.pt`,重启即可,零代码改动。
- **类名约定**:统一英文 snake_case(`scratch/crack/stain`),中文展示放前端。类名内嵌在 `.pt` 里,detector 自动读到;但双方要对齐命名。
- **对齐点**:类名命名、`imgsz`(现 640)、ultralytics 版本别差太多。

---

## 六、分阶段(先 RAG 后 Agent)

| 阶段 | 内容 | 里程碑 |
|---|---|---|
| **1 MVP(RAG)** | `rag/` 切块+嵌入+检索 + 灌 3-5 条 SOP 种子 + `api.py` 端点 `/agent/dispose?record_id=xxx`(import app.db 读 top_label → 检索 SOP → 返回处置+来源),挂 main.py 单端口 :8787 | 上传图→检出→调端点→出 SOP |
| **2 Agent** | `agent/` Function Calling 编排(查SOP+查历史+给步骤)+ `hitl/` 高危确认 | /agent/dispose 返回多步方案+待确认 |
| **3 前端** | 在看板加「处置建议」入口(经周靖同意动 `static/`)消费 /agent/dispose | 可演示完整闭环 |
| **4 可选** | Docker compose 一键起 | 部署级 |

---

## 七、环境

- Windows;Python 3.13;venv 在 `D:\Desktop\ShopInspect\.venv`(torch/ultralytics/fastapi 已装)。**rag_agent 的 langchain/chroma 装进同一个 venv**(单进程共用)。
- 你用 PyCharm(图形化),AI 用 Bash(Git Bash,`source .venv/Scripts/activate`)。
- SiliconFlow key 放 `rag_agent/.env`(gitignore),**不进 git**。
- pip 镜像:`-i https://mirrors.aliyun.com/pypi/simple`;`PYTHONUTF8=1`。

---

## 八、协作约束

- **本仓库是何承恩的 fork,非"只读"——可改 `app/`/`scripts/`/`static/`/`config.yaml`**。规则按改动幅度分:
  - **小优化/增强(直接做)**:加 UI 入口、内联按钮、样式微调、补注释、小 bugfix、版本号 bump、加路由/端点、config 加字段、scripts 加工具脚本——默认就做,commit 里写清。
  - **大改(改前确认何承恩)**:重写检测/历史/摄像头核心逻辑、改 records 表结构或字段、动数据迁移、改核心架构(如检测→推理→落库主链路)、删既有功能。
  - 界线模糊时,默认归"小优化"先做,但在 commit message 和汇报里点明,便于事后回看/回退。
- rag_agent 的核心代码仍集中在 `rag_agent/`(职责清晰、PR 好看);`app/` 的接入点不再限于"main.py 一行"。
- 分支 `feature/rag-agent`;**不自动 push**(你说推才推)。
- commit 不加 Co-Authored-By;**key 不进 git / 命令行 / commit message**。
- 权重 / venv / 日志 / `runs/` 不进 git(`.gitignore` 已忽略 `*.pt`/`data/*.db`/`.venv`/`*.log`,再加 `runs/`)。
- **本文档(HANDOFF / INTEGRATION_PLAN)是活文档,决策变了就改,不是铁律。**

---

## 九、push 说明

当前 `D:\Desktop\ShopInspect` 是原版 clone(lenhui731)。推到你自己 fork 前:
```
git remote set-url origin https://github.com/xuzhili835/ShopInspect.git
```
README / 简历标注:「在 ShopInspect(合作者周靖负责检测工程闭环)基础上,我新增缺陷模型训练 + rag_agent(RAG 缺陷处置 + Agent)」。

---

## 十、参考仓库

| 项目 | 仓库 | 用途 |
|---|---|---|
| ShopInspect(原版) | https://github.com/lenhui731/ShopInspect | 周靖的视觉检测主体(你 fork 之上新增 rag_agent) |
| ShopInspect(你的 fork) | https://github.com/xuzhili835/ShopInspect | 推送目标,push 前 `git remote set-url origin` 指向这里 |
| Smart Factory Predictive Maintenance | https://github.com/sudhindrakni2808/smart-factory-predictive-maintenance | 工业预测性维护参考——**借鉴思路**(风险评分/历史趋势预警,塞进 Agent 层),数据形态不同**代码不搬** |
