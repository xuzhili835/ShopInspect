# ShopInspect 融合项目 · 交接提示词(复制全文发给接手的 AI)

> 把本文件全文复制给接手的 AI(新会话/别的工具),它就能接着做,不用你再讲背景。

---

## 你是谁、在帮谁
你是接手这个项目的 AI 工程师。协作对象:**何承恩**(本科生,吉首大学软件工程,Java 栈为主力,本项目用全 Python)。他和同学 **周靖** 合作做 ShopInspect。
- **分工**:
  - 周靖 → 视觉检测**工程闭环**(FastAPI + SQLite + 看板 + 摄像头)+ 通用检测(已完成 V1.3)。
  - **何承恩 → 缺陷模型训练 + 缺陷处置 RAG + Agent 模块**(本提示词的任务)。
- 之前有过一个 Java 方案(`backend-java/`),**已废弃,改全 Python** 和周靖统一栈。
- 分工变更:缺陷模型原计划周靖训,现改由**何承恩自己训**。

## 参考仓库(动手前可看)
- **ShopInspect(原版)**:https://github.com/lenhui731/ShopInspect — 周靖的视觉检测主体。
- **ShopInspect(何承恩 fork)**:https://github.com/xuzhili835/ShopInspect — 推送目标。
- **Smart Factory Predictive Maintenance**:https://github.com/sudhindrakini2808/smart-factory-predictive-maintenance — **借鉴思路**(风险评分/历史趋势预警),数据形态不同**代码不搬**。

## 项目:ShopInspect(车间质检台)
- 定位:工业产线外观质检应用台。摄像头/图片 → YOLO 推理 → FastAPI → SQLite 追溯 → Web 看板。
- 技术栈:Python 3.13、FastAPI、Ultralytics YOLO11、SQLite、原生 JS 前端。
- 本地路径:`D:\Desktop\ShopInspect`(原版 clone;push 前改 remote:`git remote set-url origin https://github.com/xuzhili835/ShopInspect.git`)。
- 服务已跑通:`source .venv/Scripts/activate && python scripts/run_api.py` 起 `:8787`,权重 `yolo11n.pt`(根目录,通用 COCO)。

## 动手前必读(按顺序)
1. `D:\Desktop\ShopInspect\CURRENT_PROGRESS.md`(周靖的进度真源,看已完成、别重做)
2. `app/main.py`(FastAPI 路由)、`app/db.py`(records 表+CRUD+stats)、`app/schemas.py`(数据结构)、`app/detector.py`(YOLO 封装)、`config.yaml`
3. `INTEGRATION_PLAN.md`(融合方案 v3,单进程单端口)

## ShopInspect 接口(可供 rag_agent 消费)
- `GET /records`(筛 source/label/work_order/batch_id)、`GET /records/{id}`(详情,含 detections 框)、`GET /stats`(by_label/alert_records)、`GET /health`
- **rag_agent 实际读法**:同进程 `from app.db import get_record / list_records / stats`(单进程,不走网络)。HTTP 接口作调试通道。
- 关键字段:`status`(alert=检出 / clear=无)、`top_label`、`labels`({类:计数})、`work_order`/`batch_id`、`detections[]`、`source`、`created_at`
- alert 语义:V1 是"检出任何物体"(通用 COCO 权重);V2 切了**何承恩的缺陷模型**后才是真缺陷告警。rag_agent 消费 alert 即可。

## 何承恩负责的模块:`rag_agent/`(全 Python,新增)
**接入原则(单端口)**:
- rag_agent 核心代码集中在 `rag_agent/` 目录。**本仓库是何承恩的 fork,可改 `app/`/`scripts/`/`static/`/`config.yaml`**——不再限制"只加 main.py 一行"。
- **小优化/增强可直接做**:加 UI 入口/按钮、样式微调、补注释、小 bugfix、config 加字段、加路由/脚本。**大改先确认**:重写检测/历史核心逻辑、改 records 表结构、动数据迁移、改主架构、删既有功能。模糊时默认当小优化做,commit/汇报里点明。
- 一个进程、一个端口 `:8787`、一条命令起。读记录走同进程 `import app.db`,**不走 REST 网络**。
- langchain/chroma 装进 ShopInspect **共用 `.venv`**。
- 分支:`feature/rag-agent`。不自动 push(何承恩说推才推)。
- 权重 / venv / 日志 / `runs/` 不进 git(`.gitignore` 已忽略 `*.pt`/`data/*.db`/`.venv`/`*.log`,你再加 `runs/`)。
- **本文件和 `INTEGRATION_PLAN.md` 是活文档,决策变了就改,不是铁律。**

**模块结构**:
```
rag_agent/
  __init__.py
  rag/         # chunker + embedder(bge-m3 via SiliconFlow)+ Chroma + retriever + 来源引用
  agent/       # 处置编排:Function Calling(查SOP/查历史/给步骤),LangGraph
  hitl/        # 高危操作人工确认
  api.py       # FastAPI 路由,挂 app/main.py 单端口 :8787/agent
  data/sop/    # 缺陷维修 SOP 语料(种子:划痕/裂纹/脏污)
  README.md
```

## 技术选型
- **全 Python**(和周靖统一栈)。
- **Embedding**:bge-m3(1024 维),走 **SiliconFlow**(OpenAI 兼容);**Chat**:Qwen3-30B-A3B(同 SiliconFlow key)。
  - 取舍:SOP 语料会过 SiliconFlow,确认不涉密即可;涉密则换本地 `HuggingFaceEmbeddings`,上层不动。
- **RAG / Agent 用 LangChain + LangGraph**(Python 主流框架,**不手写**);向量库用 **Chroma**(本地持久化)。慧医云手搓过懂底层,本项目用 LangChain 工程化——简历互补。
- pip 镜像:`-i https://mirrors.aliyun.com/pypi/simple`(国内);`PYTHONUTF8=1`(中文 Windows)。

## 缺陷模型训练与交付(何承恩的活)
- 何承恩自备缺陷图片 + 标注,Ultralytics 训练,产物 `def_best.pt`。
- 交付周靖走 **GitHub Release**(tag=`model-defect-vN`,附件 `.pt` + release notes 写类名清单/imgsz/版本/指标)。**不进 git**。
- 周靖接入:改 `config.yaml: model_path → models/def_best.pt`,重启,零代码改动。
- 类名统一英文 snake_case;对齐 `imgsz=640`、ultralytics 版本。

## 何承恩要做的(LangChain 给管道,你给业务规则)
scope 隔离 → LangChain `metadata` filter(缺陷类);防幻觉 → retriever `score_threshold`(= min-score)+ 无命中拒答(你写)+ 来源引用(Document metadata);增量 → `VectorStore.add/delete`;语料(缺陷 SOP)/ prompt / 业务编排 / HITL(LangGraph)。

## 分阶段(先 RAG 后 Agent)

**阶段 1(MVP,RAG)—— 现在就做**
1. `rag_agent/rag/`:chunker + embedder(bge-m3 via SiliconFlow)+ Chroma + retriever(min-score + 来源)。
2. `rag_agent/data/sop/`:灌 3-5 条缺陷 SOP 种子(按缺陷类:划痕 / 裂纹 / 脏污 的维修步骤 md)。
3. `rag_agent/api.py`:端点 `GET /agent/dispose?record_id=xxx` → 同进程 `app.db.get_record(id)` 取 `top_label` → RAG 检索该缺陷 SOP → 返回处置文本 + 来源引用。
4. 端点挂法:`app/main.py` 加一行 `app.include_router(rag_router, prefix="/agent")`,**单端口 :8787/agent**。
5. 联调:ShopInspect :8787 出 alert → 点/调 :8787/agent/dispose → 出 SOP。
6. 里程碑:能演示「上传图 → 检出 → 调你的端点 → 出处置 SOP + 来源」。

**阶段 2(Agent)**
- `rag_agent/agent/`:Function Calling 编排(LangChain tool calling + LangGraph 状态机)。工具:查 SOP(=RAG)、查历史同类(读 records)、给处置步骤。模型 Qwen3。
- `rag_agent/hitl/`:高危步骤(停机 / 换件)人工确认接口。
- `/agent/dispose` 升级为返回多步方案 + 待确认项。

**阶段 3(前端)**:在看板加「处置建议」入口(经周靖同意动 `static/`),消费 `/agent/dispose`。

**阶段 4(可选)**:Docker compose 一键起(Python + 前端)。

## 环境 / 工程约束
- Windows;Python 3.13;venv 已建在 `D:\Desktop\ShopInspect\.venv`(torch/ultralytics/fastapi 已装)。rag_agent 的 langchain/chroma **装进同一个 venv**(单进程共用)。
- 何承恩用 PyCharm(图形化跑);你执行用 Bash(Git Bash)。
- **SiliconFlow key**:放 `rag_agent/.env`(gitignore),不进 git、不进命令行明文、不进 commit message。
- commit **不加 Co-Authored-By**;**不自动 push**;密钥不进 git。
- Maven/Java 不用(废弃)。

## 第一步(接到本提示词后立刻做)
1. 读上面"必读文件"。
2. `git checkout -b feature/rag-agent`。
3. 建 `rag_agent/` 骨架(目录 + `__init__.py` + README + .gitignore + requirements)。
4. 做 `rag_agent/rag/` MVP(chunker + embedder via SiliconFlow + Chroma + retriever)+ 灌 3-5 条 SOP 种子。
5. `rag_agent/api.py` + `app/main.py` 挂载路由(`include_router`,prefix=/agent),端点 `/agent/dispose?record_id=xxx`,单端口 :8787/agent。
6. 联调验证:上传图出 alert → 调用 → 出 SOP + 来源。

## 不要做(禁忌)
- **大改要先确认何承恩**:重写检测/历史/摄像头核心逻辑、改 records 表结构/字段、动数据迁移、改主架构(检测→推理→落库主链路)、删既有功能。
- 小优化/增强(加 UI 入口/按钮、样式、注释、bugfix、config 加字段、加路由/脚本)**可直接做**,commit/汇报里写清即可。
- 不自动 push、不把 key 进 git、commit 不加 Co-Authored-By。
- 不自动 push、不把 key 进 git、commit 不加 Co-Authored-By。
- 不重做周靖已完成项(先读 CURRENT_PROGRESS.md)。

## 简历/面试讲法(何承恩用)
> ShopInspect 是和同学合作的工业质检项目。周靖做检测工程闭环(FastAPI/SQLite/看板),我负责**缺陷模型训练 + 缺陷处置的 RAG + Agent**。检测出缺陷 → RAG 查维修 SOP → Agent 给处置步骤 → 高危人工确认。基于 **LangChain + LangGraph**(bge-m3 嵌入 + Qwen3 对话),工程化 RAG + Function Calling + HITL;单进程单端口接入,同进程读检测记录。
