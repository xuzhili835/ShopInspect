# defect_model — NEU-DET 缺陷检测模型训练

何承恩负责。基于 Ultralytics YOLO11 在 NEU-DET(钢材表面缺陷 6 类)上训练缺陷检测模型,产物交付周靖接入 ShopInspect。

## 类名(内嵌进权重,与 rag_agent SOP 对齐)
`crazing / inclusion / patches / pitted_surface / rolled-in_scale / scratches`

## 数据
NEU-DET(1800 张 200×200 灰度,6 类)。`dataset/` 已 gitignore。

## 训练(CPU)
```bash
python -m defect_model.train                         # 默认 epochs=50 imgsz=320
python -m defect_model.train --epochs 20 --imgsz 256 # 快速 demo(几十分钟)
```

## 产物
- 训练输出:`runs/defect/neu/`(gitignore)
- 交付权重:`models/def_best.pt`(gitignore)→ 走 GitHub Release

## 周靖接入
改 `config.yaml: model_path: models/def_best.pt`,重启即可,零代码改动。

## 对齐点
类名英文 snake_case;`imgsz=320`;ultralytics 版本与 ShopInspect 一致(现 8.4.118)。
