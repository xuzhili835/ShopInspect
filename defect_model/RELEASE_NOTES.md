# model-defect-v1 · NEU-DET 缺陷检测模型

何承恩训练,交付周靖接入 ShopInspect。

## 模型
- 文件:`def_best.pt`(5.4 MB)
- 基础:`yolo11n.pt`(Ultralytics YOLO11n)
- 数据:NEU-DET 钢材表面缺陷(1800 张,6 类)

## 类名(内嵌权重,与 rag_agent SOP 对齐)
| id | 类名 (snake_case) | 中文 |
|---|---|---|
| 0 | crazing | 龟裂 |
| 1 | inclusion | 夹杂物 |
| 2 | patches | 斑块 |
| 3 | pitted_surface | 麻点 |
| 4 | rolled-in_scale | 氧化铁皮压入 |
| 5 | scratches | 划痕 |

## 训练配置
- epochs=50,imgsz=256,batch=8,device=cpu,optimizer=AdamW
- 耗时:1.08 小时

## 验证集指标(30 张)
- **mAP50:0.817**
- mAP50-95:0.481
- Precision:0.741 / Recall:0.783
- 推理速度:27.6 ms/张(CPU)

## 周靖接入(零代码改动)
`config.yaml` 改一行:`model_path: models/def_best.pt`,重启即可。

## 对齐点
- 类名统一英文 snake_case(中文展示放前端)
- 推理 imgsz 建议 256(与训练一致)
- ultralytics 版本 8.4.118
