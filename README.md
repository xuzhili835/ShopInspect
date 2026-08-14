# 车间质检台 · ShopInspect

面向产线工位的外观质检 **应用台**（V1.3）：摄像头 / 图片检测 → YOLO 推理 → FastAPI → SQLite 追溯 → Web 看板。

> **定位：AI 应用工程师作品。**  
> 目标是把视觉模型接到可演示、可追溯的业务闭环，而不是自研缺陷 mAP。  
> V1 使用官方通用 YOLO 权重验证通路；缺陷专用权重预留 `models/defect_best.pt`（V2）。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com/)
[![YOLO](https://img.shields.io/badge/Ultralytics-YOLO11-red)](https://docs.ultralytics.com/)

---

## 本 fork 新增（V2，基于上游 V1.3）

本 fork（[xuzhili835/ShopInspect](https://github.com/xuzhili835/ShopInspect)）基于 [lenhui731/ShopInspect](https://github.com/lenhui731/ShopInspect)（检测工程闭环 V1.3），新增两块能力。以下正文保持上游原版 README 不变。

1. **缺陷检测模型 `defect_model/`**：NEU-DET 数据集（钢材表面 6 类缺陷）自训 `def_best.pt`，mAP50=0.817，CPU ~28ms/张。权重经 [Release model-defect-v1](https://github.com/xuzhili835/ShopInspect/releases/tag/model-defect-v1) 分发（`*.pt` 不进 git）；下载后放 `models/`，`config.yaml → model_path` 即切换。
2. **缺陷处置 `rag_agent/`（RAG + Agent + HITL）**：检测出缺陷 → RAG 查维修 SOP（bge-m3 + Chroma，带来源引用与拒答）→ Agent 多步处置方案（LangGraph ReAct，查 SOP + 查历史）→ 高危动作（换件 / 停机等）人工确认。LangChain + LangGraph，单进程单端口挂载（`/agent`），看板侧栏新增「缺陷处置」页。

上游 V2+ 预留清单中的「缺陷自训模型」「缺陷 SOP 知识库（RAG）」两项已在本 fork 实现，其余预留项见文末。

### fork 额外的安装步骤

```powershell
# rag_agent 依赖（langchain / chromadb 等，装同一 venv）
pip install -r rag_agent/requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# 密钥：复制模板后填 SiliconFlow API key（不进 git）
copy rag_agent\.env.example rag_agent\.env

# 首次建向量库：把 rag_agent/data/sop/*.md 灌进 Chroma
python -m rag_agent.build_index

# 缺陷权重：从 Release model-defect-v1 下载 def_best.pt 放 models/
# （未下载时可将 config.yaml 的 model_path 改回 yolo11n.pt 用通用权重）
```

---

## 为什么做这个项目

东莞及珠三角大量制造业岗位需要的是 **「模型能进工位、结果能进系统」**，不是只跑通 notebook。

ShopInspect 把检测能力收敛成一条产线可用链路：

1. **采图**：桌面摄像头窗口 / 浏览器摄像头 / 本地上传
2. **推理**：YOLO 封装（长边缩放、耗时、置信度、标注图）
3. **落库**：结构化检测结果 + 工单号 / 批次号
4. **看板**：KPI、历史筛选、详情大图、CSV 导出

适合简历展示的能力点：

- 视觉模型工程化接入（Ultralytics YOLO）
- 后端服务与数据追溯（FastAPI + SQLite）
- 产线可用的 Web 操作台（上传 / 实时检测 / 筛选导出）
- 配置驱动、可切换自训权重

---

## 功能一览（V1.3）

| 能力 | 说明 |
|------|------|
| 桌面摄像头实时检测 | `scripts/run_cam.py`（`q` 退出，`s` 保存并落库） |
| 图片 / 路径检测 | `POST /detect/image`、`POST /detect/path` |
| 网页摄像头 | 看板内 `getUserMedia`：单帧 / 连续检测 |
| 结构化结果 | label / confidence / bbox_xyxy / elapsed_ms / status |
| 工单与批次 | 检测时可填 `work_order` / `batch_id`，历史可筛 |
| 历史追溯 | SQLite `data/shopinspect.db` + 缩略图 / 详情弹窗 |
| 统计与筛选 | `GET /stats`、来源筛选、类别 chips、工单/批次筛选 |
| 导出 | `GET /records/export.csv`（UTF-8 BOM，Excel 可直接开） |
| 可切换权重 | `config.yaml` → `model_path`（预留缺陷专用模型） |

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
git clone https://github.com/lenhui731/ShopInspect.git
cd ShopInspect

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# CPU 版 torch（默认源慢可换清华等镜像）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 探测摄像头
python scripts/probe_camera.py

# 实时桌面窗口（需本机有界面）
python scripts/run_cam.py

# API + 看板
python scripts/run_api.py
# 浏览器打开 http://127.0.0.1:8787/
# Swagger:     http://127.0.0.1:8787/docs
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
| `model_path` | 默认 `yolo11n.pt`（首次自动下载；也可放到 `models/`） |
| `confidence` / `iou` / `device` | 推理阈值 |
| `max_infer_side` | 推理前长边限制，加速大图 |
| `jpeg_quality` | 标注图压缩质量 |
| `host` / `port` | 默认 `127.0.0.1:8787` |
| `db_path` | SQLite 路径 |

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

完整交互文档：启动后打开 `/docs`。

---

## 目录结构

```text
ShopInspect/
  app/                 # FastAPI + 检测 / DB / 摄像头 / 静态看板
    static/            # index.html + app.js
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
- **前端**：原生 HTML / CSS / JS 浅色企业后台看板
- **运行**：Windows + CPU 优先（可改 `device`）

---

## 设计取舍（面试可讲）

1. **先通路、后专用模型**  
   V1 用通用 YOLO 验证「采图 → 推理 → 落库 → 看板」全链路；缺陷数据集与 `defect_best.pt` 留给 V2，避免一上来卡在标注。

2. **结果可追溯优先于炫技推流**  
   每条记录带耗时、分辨率、标签、置信度、工单/批次；支持筛选与 CSV，方便和产线质检台账对齐。

3. **双摄像头通路**  
   OpenCV 桌面窗适合本机调试；浏览器摄像头适合演示与工位网页化；共用同一后端与数据库。

4. **配置驱动换权重**  
   业务侧只改 `model_path`，检测封装与 API / 看板不用重写。

---

## 简历一句话

独立完成车间质检台 **ShopInspect**：YOLO 检测 + FastAPI 服务 + SQLite 追溯 + Web 看板，支持工单/批次筛选与 CSV 导出，打通产线视觉质检应用闭环（V1 通用模型验证通路，可切换自训缺陷权重）。

仓库：https://github.com/lenhui731/ShopInspect

---

## V2+ 预留（未实现）

- 缺陷自训数据集 / `models/defect_best.pt`
- 告警规则引擎（如某类数量 ≥ N 标红 / 推送）
- Java / Spring 业务层、MES / PLC 对接
- 缺陷 SOP 知识库（RAG）
- GPU / TensorRT 加速
- WebSocket 长连接推流（当前仍是抓帧 HTTP）
- 多用户登录与权限

### 与 MES 对接（预留口径）

当前检测结果经 REST 落库，后续可由 Java 业务层消费 `/records`，或在检测成功回调中推送工单系统；V1 不实现 MES 协议本身。

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

个人作品与求职演示项目。正式产线部署前请替换为业务缺陷模型，并按工厂网络安全与隐私规范改造鉴权、存储与对接方式。