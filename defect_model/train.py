"""NEU-DET 缺陷检测模型训练。

CPU 训练,产物 runs/defect/neu/weights/best.pt → 复制为 models/def_best.pt。
交付:走 GitHub Release(tag=model-defect-vN),不进 git。

用法:
  python -m defect_model.train
  python -m defect_model.train --epochs 20 --imgsz 256   # 快速 demo
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_YAML = HERE / "data.yaml"
DEST = ROOT / "models" / "def_best.pt"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="yolo11n.pt", help="预训练权重")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=320, help="NEU-DET 原图 200x200,320 够用")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    if not DATA_YAML.exists():
        raise FileNotFoundError(f"缺少 {DATA_YAML},先准备数据集")

    model = YOLO(args.model)
    model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=4,
        project=str(ROOT / "runs" / "defect"),
        name="neu",
        exist_ok=True,
    )

    best = ROOT / "runs" / "defect" / "neu" / "weights" / "best.pt"
    if best.exists():
        DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, DEST)
        print(f"[defect_model] trained weights copied to {DEST}")
    else:
        print(f"[defect_model] WARNING: {best} not found,未复制")


if __name__ == "__main__":
    main()
