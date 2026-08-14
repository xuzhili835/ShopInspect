# CURRENT_PROGRESS · 车间质检台 ShopInspect

> 更新：2026-08-13（Asia/Shanghai）  
> 用途：跨会话续作真源。新对话先读本文件，**禁止从零重做已完成项**。

---

## 一句话状态

**V1.3 可用**：V1.2 全能力 + **工单号/批次号** 落库与筛选 + **类别 chips 筛选** + **CSV 导出**。  
版本：`0.1.3`；前端缓存：`app.js?v=013`。

---

## 项目定位

| 项 | 值 |
|----|----|
| 中文名 | 车间质检台 |
| 英文/仓库名 | ShopInspect |
| 根目录 | `A:\AI视觉\ShopInspect` |
| 角色匹配 | AI 应用工程师作品（接模型进业务，非炼大模型） |
| 用户 | 周靖；东莞方向；已有慧医 RAG 主项目，本仓库为视觉产线互补 |
| 关联任务 | 东莞 AI 应用工程师简历/技能补视觉闭环 |

---

## 已完成（勿重复）

### 工程骨架
- [x] 目录：`app/` `scripts/` `data/` `models/` `config.yaml` `requirements.txt` `README.md` `.gitignore`
- [x] venv：`ShopInspect\.venv`（torch CPU + ultralytics + fastapi 等）
- [x] 启动器（上一级）：`A:\AI视觉\启动车间质检台.cmd` / `启动看板.cmd` / `启动说明.txt`

### 检测与服务
- [x] YOLO 封装 `app/detector.py`（长边缩放 `max_infer_side`、画框、耗时、分辨率）
- [x] 摄像头 `app/camera.py` + `scripts/run_cam.py` / `probe_camera.py`
- [x] FastAPI `app/main.py`：health / stats / detect/image / detect/path / records CRUD / files / **export.csv**
- [x] SQLite `app/db.py`：自动 migrate 扩展字段
- [x] 冒烟：`scripts/smoke_test.py`；API 曾验证通过；**2026-08-13 工单/批次/CSV 冒烟通过**

### 扩展数据字段
落库/接口含：
`elapsed_ms` `conf_used` `image_width` `image_height` `labels` `top_label` `avg/max_confidence` `status(alert|clear)`  
**+ `work_order` `batch_id`（v0.1.3）**  
stats 含：`by_label` `avg_elapsed_ms` `alert_records`

### 前端（浅色企业后台）
- [x] 侧栏导航 + KPI 卡片 + 双栏（检测 | 历史）
- [x] 上传 / 摄像头模式切换
- [x] **实时检测**：检完立刻下一帧；默认不落库；overlay + LIVE fps
- [x] 历史：缩略图、来源筛选、全选、批量删、清空
- [x] **详情弹窗大图** + 字段/框表/JSON/删除
- [x] 卡死修复：完整重写 `static/app.js`（`?v=012` 起）
- [x] **工单号/批次号输入** + 列表列 + 详情展示
- [x] **类别 chips 筛选**（吃 `/stats.by_label`）+ 工单/批次筛选框
- [x] **导出 CSV**（跟当前筛选条件）

### 删除 API
- `DELETE /records/{id}`
- `POST /records/delete-batch` body `{"ids":[...]}`
- `DELETE /records?confirm=YES`

### 新增 API（v0.1.3）
- `POST /detect/image` Form 增：`work_order` `batch_id`
- `GET /records` Query 增：`work_order` `batch_id`（原有 `source` `label`）
- `GET /records/export.csv`：UTF-8 BOM CSV 下载

---

## 明确未做（V2+）

- 缺陷自训数据集 / `defect_best.pt`
- 告警规则引擎（如某类数量 ≥ N 标红/推送）
- Java/Spring 业务层、MES/PLC
- RAG 缺陷 SOP
- GPU/TensorRT 加速
- WebSocket 推流（当前仍是抓帧 HTTP）
- 多用户登录权限

---

## 怎么跑（续作必用）

```powershell
cd A:\AI视觉\ShopInspect
.\.venv\Scripts\Activate.ps1
python scripts\run_api.py
# http://127.0.0.1:8787/   Ctrl+F5 强刷
# 或双击 A:\AI视觉\启动看板.cmd
```

其它：
- 摄像头桌面窗：`python scripts\run_cam.py`（q 退 / s 存）
- 探测：`python scripts\probe_camera.py`
- 冒烟：`python scripts\smoke_test.py`
- 文档：`http://127.0.0.1:8787/docs`

配置：`config.yaml`（model_path / confidence / max_infer_side / device / port=8787）

---

## 关键文件

| 路径 | 职责 |
|------|------|
| `app/main.py` | API + 看板入口 + CSV 导出 |
| `app/detector.py` | YOLO |
| `app/db.py` | SQLite + migrate + stats |
| `app/schemas.py` | Pydantic |
| `app/static/index.html` | 布局/样式/弹窗 |
| `app/static/app.js` | 全部前端逻辑（**改 UI 先改这里**；当前 `?v=013`） |
| `config.yaml` | 运行配置 |
| `scripts/run_api.py` | 启动 API |

版本：`app/__init__.py` → `0.1.3`

---

## 已知注意

1. **强刷**：改前端后必须 Ctrl+F5 或改 `app.js?v=` 防缓存  
2. **实时 FPS**：CPU 上大约 1–5 fps 量级，不是工业 30fps  
3. **旧历史记录**：migrate 前写入的行，新字段可能为空；新检测才齐全  
4. **摄像头占用**：网页开着相机时，`run_cam.py` 可能抢不到  
5. **V1 模型**：通用 `yolo11n.pt`，验证闭环，**不是**产线缺陷精度  
6. 权重/输出：`*.pt`、`data/outputs/*`、`data/*.db` 已 gitignore  
7. 服务若已在跑，改代码后需**重启** `run_api.py` 才吃到后端变更  

---

## 建议下一刀（按优先级）

1. **告警规则**：如检出数 ≥ N 或指定 label → status/UI 标红  
2. 自采小样本微调缺陷模型，切换 `model_path`  
3. 工单维度 KPI（按 work_order 汇总）  
4. WebSocket / 更丝滑实时流  
5. 对接 Spring/MES 说明页

---

## 新会话续作口令（可直接粘贴）

```text
读 A:\AI视觉\ShopInspect\CURRENT_PROGRESS.md，按「建议下一刀」继续，不要重做已完成项。
当前项目：车间质检台 ShopInspect。先确认 run_api 可起，再实现下一项。
```

---

## 变更戳

| 时间 | 内容 |
|------|------|
| 2026-08-11 | V1 闭环初版:检测/API/SQLite/看板/摄像头 |
| 2026-08-11 | Web 摄像头 + 启动器 |
| 2026-08-11 | V1.1 性能与体验;V1.1+ 删除增强 |
| 2026-08-11 | 浅色企业风 UI;实时检测;详情弹窗;扩展字段 |
| 2026-08-12 | 修复 app.js 截断导致页面卡死;排版收敛;写本进度真源 |
| 2026-08-13 | V1.3:工单号/批次号 + 类别筛选 UI + CSV 导出;版本 0.1.3 |
| 2026-08-14 | **fork(何承恩)UI 整修 v0.1.4**,见下节 |

---

## fork 侧 UI 整修(2026-08-14,何承恩分支 feature/rag-agent)

基于 UI 自查(代码审读 + 有头浏览器实测)分三刀修复,版本 `0.1.4`,前端缓存 `?v=017`:

1. **第一刀(704a258)**:Agent 处置方案渲染 Markdown(自写轻量渲染:粗体/标题/列表/编号徽章/【】高亮,看板弹窗与处置工作台两处);处置工作台重做——最近记录点选(alert 优先)替代手抄 ID、去掉写死的默认 ID 9、查询中禁用按钮、高危确认改事件委托、配色与主看板统一(青绿);副标题版本更新。
2. **第二刀(83bc9a4)**:后端 `/records` 与 CSV 导出加 `status` 筛选;历史工具栏「⚑ 只看告警」;「清除」筛选彻底复位(含来源+告警开关,原先残留);历史分页(50/页 + 加载更多 + 计数);切回上传模式自动关摄像头流。
3. **第三刀(b4e0369)**:历史/弹窗字段统一 escapeHtml(XSS 对抗验证:工单号注入 onerror 不执行);删死代码(#detailBox/#btnDeleteOne);内联 SVG favicon(控制台 0 错误);KPI 卡正名「类别分布」。

动到的文件:`app/static/index.html` `app/static/app.js` `rag_agent/ui.html` `app/db.py` `app/main.py`(仅加 status 查询参数,不动表结构)。
