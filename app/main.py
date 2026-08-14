"""FastAPI entry: health / detect / records + web dashboard."""
from __future__ import annotations

import csv
import io
import base64
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings, load_settings
from app.db import (
    clear_all_records,
    count_records,
    delete_many,
    delete_record,
    get_record,
    init_db,
    insert_record,
    list_all_image_paths,
    list_image_paths_by_ids,
    list_records,
    stats as db_stats,
    summarize_detections,
)
from app.detector import get_detector
from app.schemas import (
    DetectResponse,
    DetectionItem,
    HealthResponse,
    PathDetectRequest,
    RecordDetail,
    RecordSummary,
    StatsResponse,
)

settings = load_settings()
init_db(settings)

static_dir = Path(__file__).resolve().parent / "static"
outputs_dir = settings.outputs_path
outputs_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(settings)
    try:
        get_detector().load()
        print(f"[ShopInspect] model loaded: {settings.model_path} device={settings.device}")
    except Exception as e:  # noqa: BLE001
        print(f"[ShopInspect] model preload skipped: {e}")
    yield


app = FastAPI(
    title=f"{settings.app_name} ({settings.app_name_en})",
    version=__version__,
    description="车间外观质检应用台：检测 + 落库 + 看板",
    lifespan=lifespan,
)

# rag_agent 接入(单进程单端口):langchain 栈未装时跳过,不影响 ShopInspect 主功能
try:
    from rag_agent.api import router as _rag_router

    app.include_router(_rag_router, prefix="/agent")
    print("[ShopInspect] rag_agent enabled at /agent")
except Exception as _rag_e:  # noqa: BLE001
    print(f"[ShopInspect] rag_agent disabled: {_rag_e}")

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _rel_to_abs(rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return p
    return (settings.project_root / p).resolve()


def _encode_jpg_b64(img_bgr: np.ndarray) -> str:
    q = int(getattr(settings, "jpeg_quality", 85) or 85)
    ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), max(40, min(95, q))])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _to_detect_response(
    result,
    record_id: int | None,
    include_annotated: bool,
    work_order: str | None = None,
    batch_id: str | None = None,
) -> DetectResponse:
    annotated_b64 = None
    if include_annotated and result.annotated_bgr is not None:
        annotated_b64 = _encode_jpg_b64(result.annotated_bgr)
    summary = summarize_detections(result.detections)
    return DetectResponse(
        id=record_id,
        created_at=result.created_at,
        source=result.source,  # type: ignore[arg-type]
        image_path=result.image_path,
        num_detections=result.num_detections,
        detections=[DetectionItem(**d) for d in result.detections],
        model=result.model,
        note=result.note,
        annotated_base64=annotated_b64,
        elapsed_ms=float(round(result.elapsed_ms, 1)),
        conf_used=result.conf_used,
        image_width=getattr(result, "image_width", None),
        image_height=getattr(result, "image_height", None),
        labels=summary.get("labels") or {},
        top_label=summary.get("top_label"),
        avg_confidence=summary.get("avg_confidence"),
        max_confidence=summary.get("max_confidence"),
        status=summary.get("status"),
        work_order=(work_order or "").strip() or None,
        batch_id=(batch_id or "").strip() or None,
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> Response:
    index = static_dir / "index.html"
    if not index.exists():
        return HTMLResponse("<h1>ShopInspect</h1><p>static/index.html missing</p>")
    # avoid browser caching old UI during迭代
    return HTMLResponse(
        index.read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    det = get_detector()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        app_en=settings.app_name_en,
        model=settings.model_path,
        device=settings.device,
        model_loaded=bool(det.loaded),
        camera_index=settings.camera_index,
        version=__version__,
    )


@app.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    s = db_stats()
    return StatsResponse(
        total_records=s["total_records"],
        total_detections=s["total_detections"],
        by_source=s["by_source"],
        by_label=s.get("by_label") or {},
        avg_elapsed_ms=s.get("avg_elapsed_ms"),
        alert_records=int(s.get("alert_records") or 0),
        model=settings.model_path,
        device=settings.device,
    )


@app.post("/detect/image", response_model=DetectResponse)
async def detect_image(
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
    work_order: Optional[str] = Form(None),
    batch_id: Optional[str] = Form(None),
    return_annotated: Optional[bool] = Form(None),
    save: bool = Form(True),
    source: str = Form("upload"),
    conf: Optional[float] = Form(None),
) -> DetectResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    # soft limit ~12MB
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "image too large (>12MB)")
    arr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "cannot decode image")

    src = (source or "upload").strip().lower()
    if src not in {"upload", "camera", "path", "file"}:
        src = "upload"

    conf_arg = None
    if conf is not None:
        try:
            conf_arg = float(conf)
        except (TypeError, ValueError):
            conf_arg = None
        if conf_arg is not None and not (0.01 <= conf_arg <= 0.99):
            raise HTTPException(400, "conf must be between 0.01 and 0.99")

    include_ann = (
        settings.return_annotated_default if return_annotated is None else return_annotated
    )
    try:
        det = get_detector()
        result = det.predict_bgr(frame, source=src, note=note, conf=conf_arg)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"detect failed: {e}") from e

    record_id = None
    if save:
        det.save_annotated(result, prefix=src if src in {"camera", "upload"} else "upload")
        record_id = insert_record(
            created_at=result.created_at,
            source=result.source,
            image_path=result.image_path,
            num_detections=result.num_detections,
            detections=result.detections,
            model=result.model,
            note=note,
            elapsed_ms=result.elapsed_ms,
            conf_used=result.conf_used,
            image_width=getattr(result, "image_width", None),
            image_height=getattr(result, "image_height", None),
            work_order=work_order,
            batch_id=batch_id,
        )

    return _to_detect_response(
        result, record_id, include_ann, work_order=work_order, batch_id=batch_id
    )


@app.post("/detect/path", response_model=list[DetectResponse])
def detect_path(body: PathDetectRequest) -> list[DetectResponse]:
    path = Path(body.path)
    if not path.is_absolute():
        path = (settings.project_root / path).resolve()
    if not path.exists():
        raise HTTPException(404, f"path not found: {path}")

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if path.is_file():
        files = [path]
    else:
        pattern = "**/*" if body.recursive else "*"
        files = sorted(
            p for p in path.glob(pattern) if p.is_file() and p.suffix.lower() in exts
        )
    if not files:
        raise HTTPException(400, "no images found")
    if len(files) > 100:
        raise HTTPException(400, "too many images (>100); narrow the folder")

    det = get_detector()
    out: list[DetectResponse] = []
    for fp in files:
        try:
            result = det.predict_path(fp, source="path", note=body.note)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"detect failed on {fp}: {e}") from e
        record_id = None
        if body.save:
            det.save_annotated(result, prefix=fp.stem[:40] or "path")
            record_id = insert_record(
                created_at=result.created_at,
                source=result.source,
                image_path=result.image_path,
                num_detections=result.num_detections,
                detections=result.detections,
                model=result.model,
                note=body.note,
                elapsed_ms=result.elapsed_ms,
                conf_used=result.conf_used,
                image_width=getattr(result, "image_width", None),
                image_height=getattr(result, "image_height", None),
                work_order=body.work_order,
                batch_id=body.batch_id,
            )
        out.append(
            _to_detect_response(
                result,
                record_id,
                include_annotated=False,
                work_order=body.work_order,
                batch_id=body.batch_id,
            )
        )
    return out


@app.get("/records", response_model=list[RecordSummary])
def records(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    work_order: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
) -> list[RecordSummary]:
    rows = list_records(
        limit=limit,
        offset=offset,
        source=source,
        label=label,
        work_order=work_order,
        batch_id=batch_id,
    )
    return [RecordSummary(**r) for r in rows]


@app.get("/records/export.csv")
def records_export_csv(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    work_order: Optional[str] = Query(None),
    batch_id: Optional[str] = Query(None),
):
    rows = list_records(
        limit=limit,
        offset=offset,
        source=source,
        label=label,
        work_order=work_order,
        batch_id=batch_id,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "created_at",
            "source",
            "work_order",
            "batch_id",
            "num_detections",
            "top_label",
            "avg_confidence",
            "max_confidence",
            "status",
            "elapsed_ms",
            "conf_used",
            "image_width",
            "image_height",
            "model",
            "note",
            "image_path",
            "labels",
        ]
    )
    for r in rows:
        labels = r.get("labels") or {}
        label_str = ";".join(f"{k}:{v}" for k, v in labels.items())
        writer.writerow(
            [
                r.get("id"),
                r.get("created_at"),
                r.get("source"),
                r.get("work_order") or "",
                r.get("batch_id") or "",
                r.get("num_detections"),
                r.get("top_label") or "",
                r.get("avg_confidence") if r.get("avg_confidence") is not None else "",
                r.get("max_confidence") if r.get("max_confidence") is not None else "",
                r.get("status") or "",
                r.get("elapsed_ms") if r.get("elapsed_ms") is not None else "",
                r.get("conf_used") if r.get("conf_used") is not None else "",
                r.get("image_width") if r.get("image_width") is not None else "",
                r.get("image_height") if r.get("image_height") is not None else "",
                r.get("model") or "",
                r.get("note") or "",
                r.get("image_path") or "",
                label_str,
            ]
        )
    data = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="shopinspect_records.csv"'},
    )


@app.get("/records/count")
def records_count() -> dict:
    return {"count": count_records()}


@app.get("/records/{record_id}", response_model=RecordDetail)
def record_detail(record_id: int) -> RecordDetail:
    row = get_record(record_id)
    if row is None:
        raise HTTPException(404, "record not found")
    detections = [DetectionItem(**d) for d in row.get("detections") or []]
    return RecordDetail(
        id=row["id"],
        created_at=row["created_at"],
        source=row["source"],
        image_path=row.get("image_path"),
        num_detections=row["num_detections"],
        model=row.get("model") or "",
        note=row.get("note"),
        elapsed_ms=row.get("elapsed_ms"),
        conf_used=row.get("conf_used"),
        image_width=row.get("image_width"),
        image_height=row.get("image_height"),
        labels=row.get("labels") or {},
        top_label=row.get("top_label"),
        avg_confidence=row.get("avg_confidence"),
        max_confidence=row.get("max_confidence"),
        status=row.get("status"),
        work_order=row.get("work_order"),
        batch_id=row.get("batch_id"),
        detections=detections,
        raw_json={
            "detections": row.get("detections") or [],
            "labels": row.get("labels") or {},
            "work_order": row.get("work_order"),
            "batch_id": row.get("batch_id"),
        },
    )


@app.delete("/records/{record_id}")
def record_delete(record_id: int) -> dict:
    row = get_record(record_id)
    if row is None:
        raise HTTPException(404, "record not found")
    # best-effort delete image file
    img = _rel_to_abs(row.get("image_path"))
    if img and img.exists():
        try:
            img.unlink()
        except OSError:
            pass
    ok = delete_record(record_id)
    if not ok:
        raise HTTPException(500, "delete failed")
    return {"deleted": record_id}



def _unlink_images(paths: list[str]) -> int:
    n = 0
    for rel in paths:
        abs_path = _rel_to_abs(rel)
        if abs_path and abs_path.exists():
            try:
                abs_path.unlink()
                n += 1
            except OSError:
                pass
    return n


class BatchDeleteRequest(BaseModel):
    ids: list[int] = Field(default_factory=list)


@app.post("/records/delete-batch")
def records_delete_batch(body: BatchDeleteRequest) -> dict:
    ids = sorted({int(i) for i in body.ids if int(i) > 0})
    if not ids:
        raise HTTPException(400, "ids required")
    if len(ids) > 500:
        raise HTTPException(400, "too many ids (>500)")
    paths = list_image_paths_by_ids(ids)
    removed_files = _unlink_images(paths)
    removed = delete_many(ids)
    return {"deleted": removed, "files_removed": removed_files, "ids": ids}


@app.delete("/records")
def records_clear_all(confirm: str = Query(...)) -> dict:
    if confirm != "YES":
        raise HTTPException(400, 'pass confirm=YES to clear all')
    paths = list_all_image_paths()
    removed_files = _unlink_images(paths)
    removed = clear_all_records()
    return {"deleted": removed, "files_removed": removed_files}


@app.get("/files/{file_path:path}")
def get_file(file_path: str):
    abs_path = _rel_to_abs(file_path)
    if abs_path is None or not abs_path.exists():
        raise HTTPException(404, "file not found")
    try:
        abs_path.resolve().relative_to(settings.project_root.resolve())
    except ValueError as e:
        raise HTTPException(403, "forbidden") from e
    media = mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
    return FileResponse(str(abs_path), media_type=media)
