# 车间质检台 · ShopInspect

面向产线工位的外观质检 **应用台**（V2）：摄像头 / 图片检测 → YOLO 推理 → FastAPI → SQLite 追溯 → Web 看板 → **缺陷处置 RAG + Agent**。

> **定位：AI 应用工程师作品。**  
> 目标是把视觉模型接到可演示、可追溯的业务闭环，而不是自研缺陷 mAP。  
> V2 已切换自训缺陷模型 `models/def_best.pt`（NEU-DET 6 类，mAP50=0.817），并新增 `rag_agent/` 处置模块：检测出缺陷 → RAG 查维修 SOP → Agent 给多步处置方案 → 高危动作人工确认（HITL）。

> **合作说明**：本仓库为合作项目 [lenhui731/ShopInspect](https://github.com/lenhui731/ShopInspect) 的 fork。
> 周靖负责检测工程闭环（FastAPI + SQLite + 看板 + 摄像头，V1.3）；何承恩（本 fork）新增 **缺陷模型训练 + rag_agent（RAG 缺陷处置 + Agent + HITL）**。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com/)
[![YOLO](https://img.shields.io/badge/Ultralytics-YOLO11-red)](https://docs.ultralytics.com/)
[![LangChain](https://img.shields.io/badge/LangChain-LangGraph-1C3C3C)](https://github.com/langchain-ai/langgraph)

---

## 为什么做这个项目

东莞及珠三角大量制造业岗位需要的是 **「模型能进工位、结果能进系统」**，不是只跑通 notebook。

ShopInspect 把检测能力收敛成一条产线可用链路：

1. **采图**：桌面摄像头窗口 / 浏览器摄像头 / 本地上传
2. **推理**：YOLO 封装（长边缩放、耗时、置信度、标注图）
3. **落库**：结构化检测结果 + 工单号 / 批次号
4. **看板**：KPI、历史筛选、详情大图、CSV 导出
5. **处置**（V2 新增）：检出缺陷 → RAG 查维修 SOP → Agent 多步方案 → 高危人工确认

本项目体现的工程能力点：

- 视觉模型工程化接入（Ultralytics YOLO）
- 后端服务与数据追溯（FastAPI + SQLite）
- 产线可用的 Web 操作台（上传 / 实时检测 / 筛选导出）
- 配置驱动、可切换自训权重
- RAG + Agent 工程化（LangChain / LangGraph / Chroma，Function Calling + HITL）

---

## 功能一览（V2）

| 能力 | 说明 |
|------|------|
| 桌面摄像头实时检测 | `scripts/run_cam.py`（`q` 退出，`s` 保存并落库） |
| 图片 / 路径检测 | `POST /detect/image`、`POST /detect/path` |
| 网页摄像头 | 看板内 `getUserMedia`：单帧 / 连续检测 |
| 缺陷专用模型 | `models/def_best.pt`（NEU-DET 6 类，mAP50=0.817，CPU ~28ms/张） |
| 结构化结果 | label / confidence / bbox_xyxy / elapsed_ms / status |
| 工单与批次 | 检测时可填 `work_order` / `batch_id`，历史可筛 |
| 历史追溯 | SQLite `data/shopinspect.db` + 缩略图 / 详情弹窗 |
| 统计与筛选 | `GET /stats`、来源筛选、类别 chips、工单/批次筛选 |
| 导出 | `GET /records/export.csv`（UTF-8 BOM，Excel 可直接开） |
| **缺陷处置 RAG** | `GET /agent/dispose`：按缺陷类检索维修 SOP，带来源引用 + 无命中拒答 |
| **处置 Agent** | LangGraph ReAct 编排（查 SOP + 查历史同类），出多步处置方案 |
| **高危人工确认** | 换件 / 停机等高危动作 `POST /agent/dispose/confirm` 批准后才算数 |
| **处置工作台** | `GET /agent/` 独立前端页；看板详情弹窗亦可一键看处置方案 |
| 可切换权重 | `config.yaml` → `model_path` |

### 工程优化点

- 推理前长边缩放（`max_infer_side`，默认 960）加速大图 / 摄像头
- JPEG 质量可配；API 返回 `elapsed_ms` / `conf_used`
- 连续检测默认**不落库**（可勾选落库），减少磁盘写入
- 看板：置信度滑条、来源筛选、批量删除、详情大图
- **工单号 / 批次号** 落库与筛选
- **类别 chips** 筛选 + **CSV 导出**

---

## 快速开始（Windows / CPU）

```powershell
git clone https://github.com/xuzhili835/ShopInspect.git
cd ShopInspect

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# CPU 版 torch（默认源慢可换清华等镜像）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# rag_agent 依赖（langchain / chromadb 等，装同一 venv）
pip install -r rag_agent/requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# rag_agent 密钥：复制模板后填 SiliconFlow API key（不进 git）
copy rag_agent\.env.example rag_agent\.env

# 首次建向量库：把 rag_agent/data/sop/*.md 灌进 Chroma
python -m rag_agent.build_index

# 缺陷权重 *.pt 不进 git：从 GitHub Release（model-defect-v1，若已发布）下载
# def_best.pt 放到 models/；或自己用 defect_model/train.py 训练
# （或先用通用权重：config.yaml 里 model_path 改回 yolo11n.pt）

# 探测摄像头
python scripts/probe_camera.py

# 实时桌面窗口（需本机有界面）
python scripts/run_cam.py

# API + 看板（rag_agent 随同进程一起挂载在 /agent）
python scripts/run_api.py
# 浏览器打开 http://127.0.0.1:8787/
# Swagger:     http://127.0.0.1:8787/docs
# 处置工作台:   http://127.0.0.1:8787/agent/
```

### 摄像头注意

1. Windows 设置 → 隐私和安全性 → 相机 → 允许桌面应用访问
2. 关掉 Teams / 微信 /「相机」应用占用
3. 默认 index=`0`（可在 `config.yaml` 改 `camera_index`）

### 网页摄像头

看板顶部可切换 **上传图片** / **使用摄像头**：

1. 点「使用摄像头」→「开启摄像头」（浏览器授权）
2. **拍一帧检测**：抓当前画面送 YOLO，结果可落库（source=`camera`）
3. **连续 / 实时检测**：检完立刻下一帧；默认不落库，可勾选落库
4. 不需要摄像头时保持「上传图片」即可

说明：网页走浏览器 `getUserMedia`，与 `scripts/run_cam.py`（OpenCV 桌面窗）是两条通路，结果写入同一数据库。

---

## 配置

见 `config.yaml`：

| 项 | 含义 |
|----|------|
| `model_path` | 当前 `models/def_best.pt`（自训缺陷权重；可切回 `yolo11n.pt`） |
| `confidence` / `iou` / `device` | 推理阈值 |
| `max_infer_side` | 推理前长边限制，加速大图 |
| `jpeg_quality` | 标注图压缩质量 |
| `host` / `port` | 默认 `127.0.0.1:8787` |
| `db_path` | SQLite 路径 |

rag_agent 配置独立在 `rag_agent/.env`（SiliconFlow key、嵌入/对话模型、检索阈值），不碰 `config.yaml`。

权重文件 `*.pt` 不入库；首次运行会按配置下载或读取本地模型。

---

## API 摘要

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/stats` | 统计（含 by_label / alert 等） |
| POST | `/detect/image` | multipart 上传检测；可选 `note` `conf` `work_order` `batch_id` `return_annotated` `save` |
| POST | `/detect/path` | JSON 路径检测 |
| GET | `/records` | 分页历史；可筛 `source` `label` `work_order` `batch_id` |
| GET | `/records/{id}` | 单条详情 |
| DELETE | `/records/{id}` | 删除单条 |
| POST | `/records/delete-batch` | 批量删除 |
| DELETE | `/records?confirm=YES` | 清空 |
| GET | `/records/export.csv` | 按当前筛选导出 CSV |
| GET | `/files/{relative_path}` | 访问 `data/outputs/...` 标注图 |
| GET | `/agent/dispose?record_id=X` | 缺陷处置：`use_agent=true` 走 Agent 多步方案（默认），`false` 走纯 RAG SOP |
| POST | `/agent/dispose/confirm` | 高危动作（换件/停机/报废/补焊）人工批准 / 拒绝 |
| GET | `/agent/` | 处置工作台前端页 |

完整交互文档：启动后打开 `/docs`。

---

## 目录结构

```text
ShopInspect/
  app/                 # FastAPI + 检测 / DB / 摄像头 / 静态看板（周靖）
    static/            # index.html + app.js
  rag_agent/           # 缺陷处置 RAG + Agent + HITL（何承恩）
    rag/               # chunker + bge-m3 嵌入 + Chroma + retriever
    agent/             # LangGraph ReAct 编排（查SOP/查历史/给步骤）
    hitl/              # 高危动作人工确认
    data/sop/          # 6 类缺陷维修 SOP 语料
    api.py             # /agent 路由（挂同进程 :8787/agent）
  defect_model/        # NEU-DET 训练脚本 + 交付说明（何承恩）
  scripts/             # probe / run_cam / run_api / smoke_test
  data/
    inputs/            # 上传原图（gitignore 内容）
    outputs/           # 标注图（gitignore 内容）
    shopinspect.db     # 本地库（gitignore）
  models/              # 本地权重目录（*.pt gitignore）
  config.yaml
  requirements.txt
  CURRENT_PROGRESS.md  # 跨会话续作进度
```

---

## 技术栈

- **视觉**：Ultralytics YOLO11、OpenCV、Pillow
- **服务**：FastAPI、Uvicorn、Pydantic
- **数据**：SQLite（自动 migrate 扩展字段）
- **RAG / Agent**：LangChain + LangGraph（ReAct）、Chroma 向量库、bge-m3 嵌入 + Qwen3 对话（SiliconFlow，OpenAI 兼容）
- **前端**：原生 HTML / CSS / JS 浅色企业后台看板
- **运行**：Windows + CPU 优先（可改 `device`）

---

## 设计取舍

1. **先通路、后专用模型**  
   V1 用通用 YOLO 验证「采图 → 推理 → 落库 → 看板」全链路；V2 用 NEU-DET 自训 `def_best.pt` 切换真缺陷告警，避免一上来卡在标注。

2. **结果可追溯优先于炫技推流**  
   每条记录带耗时、分辨率、标签、置信度、工单/批次；支持筛选与 CSV，方便和产线质检台账对齐。

3. **双摄像头通路**  
   OpenCV 桌面窗适合本机调试；浏览器摄像头适合演示与工位网页化；共用同一后端与数据库。

4. **配置驱动换权重**  
   业务侧只改 `model_path`，检测封装与 API / 看板不用重写。

5. **处置模块单进程接入，不动检测主链路**  
   rag_agent 只在 `app/main.py` 挂一个 `include_router`，同进程 `import app.db` 读记录（不走网络）；RAG 用 metadata 按缺陷类隔离 + score_threshold 防幻觉 + 来源引用，高危动作必须 HITL 确认。

6. **AI 能力走 API、工程自己写**  
   嵌入（bge-m3）和对话（Qwen3）走 SiliconFlow API，SOP 语料若涉密可换本地嵌入、上层不动；检索阈值、拒答、业务编排、HITL 规则都是自己写的业务逻辑。

---

## V3+ 预留（未实现）

- 告警规则引擎（如某类数量 ≥ N 标红 / 推送）
- MES / PLC 对接（Java 业务层方案已废弃，统一全 Python）
- GPU / TensorRT 加速
- WebSocket 长连接推流（当前仍是抓帧 HTTP）
- 多用户登录与权限
- SOP 语料管理界面（当前加 SOP = 丢 md 进 `rag_agent/data/sop/` 重建库）

### 已在 V2 完成（原预留项）

- ✅ 缺陷自训模型 `models/def_best.pt`（NEU-DET，mAP50=0.817，交付见 `defect_model/RELEASE_NOTES.md`）
- ✅ 缺陷 SOP 知识库 + 处置 Agent（`rag_agent/`，见其 README）

### 与 MES 对接（预留口径）

当前检测结果经 REST 落库，后续可由业务层消费 `/records`，或在检测成功回调中推送工单系统；V2 不实现 MES 协议本身。

---

## 冒烟与续作

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\smoke_test.py
python scripts\run_api.py
```

跨会话进度见 `CURRENT_PROGRESS.md`。

---

## License / 说明

合作项目（周靖：检测工程闭环；何承恩：缺陷模型 + rag_agent），个人作品与求职演示用途。正式产线部署前请替换为业务缺陷模型，并按工厂网络安全与隐私规范改造鉴权、存储与对接方式。