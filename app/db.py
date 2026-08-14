"""SQLite persistence for detection records."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    image_path TEXT,
    num_detections INTEGER NOT NULL DEFAULT 0,
    detections_json TEXT NOT NULL,
    model TEXT,
    note TEXT,
    elapsed_ms REAL,
    conf_used REAL,
    image_width INTEGER,
    image_height INTEGER,
    labels_json TEXT,
    top_label TEXT,
    avg_confidence REAL,
    max_confidence REAL,
    status TEXT,
    work_order TEXT,
    batch_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_records_created_at ON records(created_at DESC);
"""

EXTRA_COLUMNS = {
    "elapsed_ms": "REAL",
    "conf_used": "REAL",
    "image_width": "INTEGER",
    "image_height": "INTEGER",
    "labels_json": "TEXT",
    "top_label": "TEXT",
    "avg_confidence": "REAL",
    "max_confidence": "REAL",
    "status": "TEXT",
    "work_order": "TEXT",
    "batch_id": "TEXT",
}


def connect(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    db_path = settings.db_file
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()}
    for name, typ in EXTRA_COLUMNS.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE records ADD COLUMN {name} {typ}")


def init_db(settings: Settings | None = None) -> None:
    conn = connect(settings)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_source ON records(source)")
        # top_label index only after migrate ensures column exists
        cols = {r[1] for r in conn.execute("PRAGMA table_info(records)").fetchall()}
        if "top_label" in cols:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_top_label ON records(top_label)")
        if "work_order" in cols:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_work_order ON records(work_order)")
        if "batch_id" in cols:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_batch_id ON records(batch_id)")
        conn.commit()
    finally:
        conn.close()


def summarize_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    labels: dict[str, int] = {}
    confs: list[float] = []
    for d in detections or []:
        lab = str(d.get("label") or "unknown")
        labels[lab] = labels.get(lab, 0) + 1
        try:
            confs.append(float(d.get("confidence") or 0))
        except (TypeError, ValueError):
            pass
    top_label = None
    if labels:
        top_label = sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    avg_c = round(sum(confs) / len(confs), 4) if confs else None
    max_c = round(max(confs), 4) if confs else None
    status = "alert" if (detections and len(detections) > 0) else "clear"
    # For general COCO demo, "alert" just means objects found; UI can style it.
    return {
        "labels": labels,
        "top_label": top_label,
        "avg_confidence": avg_c,
        "max_confidence": max_c,
        "status": status,
    }


def insert_record(
    *,
    created_at: str,
    source: str,
    image_path: str | None,
    num_detections: int,
    detections: list[dict[str, Any]],
    model: str,
    note: str | None = None,
    elapsed_ms: float | None = None,
    conf_used: float | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    work_order: str | None = None,
    batch_id: str | None = None,
    settings: Settings | None = None,
) -> int:
    init_db(settings)
    summary = summarize_detections(detections)
    conn = connect(settings)
    try:
        cur = conn.execute(
            """
            INSERT INTO records (
                created_at, source, image_path, num_detections, detections_json,
                model, note, elapsed_ms, conf_used, image_width, image_height,
                labels_json, top_label, avg_confidence, max_confidence, status,
                work_order, batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                source,
                image_path,
                num_detections,
                json.dumps(detections, ensure_ascii=False),
                model,
                note,
                elapsed_ms,
                conf_used,
                image_width,
                image_height,
                json.dumps(summary["labels"], ensure_ascii=False),
                summary["top_label"],
                summary["avg_confidence"],
                summary["max_confidence"],
                summary["status"],
                (work_order or "").strip() or None,
                (batch_id or "").strip() or None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_records(
    *,
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
    label: str | None = None,
    work_order: str | None = None,
    batch_id: str | None = None,
    status: str | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    init_db(settings)
    conn = connect(settings)
    try:
        sql = """
            SELECT id, created_at, source, image_path, num_detections, model, note,
                   elapsed_ms, conf_used, image_width, image_height, labels_json,
                   top_label, avg_confidence, max_confidence, status,
                   work_order, batch_id
            FROM records
            WHERE 1=1
        """
        params: list[Any] = []
        if source:
            sql += " AND source = ?"
            params.append(source)
        if label:
            sql += " AND (top_label = ? OR labels_json LIKE ?)"
            params.append(label)
            params.append(f'%"{label}"%')
        if work_order:
            sql += " AND work_order = ?"
            params.append(work_order)
        if batch_id:
            sql += " AND batch_id = ?"
            params.append(batch_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["labels"] = json.loads(d.pop("labels_json") or "{}")
            except json.JSONDecodeError:
                d["labels"] = {}
                d.pop("labels_json", None)
            out.append(d)
        return out
    finally:
        conn.close()


def get_record(record_id: int, settings: Settings | None = None) -> dict[str, Any] | None:
    init_db(settings)
    conn = connect(settings)
    try:
        row = conn.execute(
            """
            SELECT id, created_at, source, image_path, num_detections,
                   detections_json, model, note, elapsed_ms, conf_used,
                   image_width, image_height, labels_json, top_label,
                   avg_confidence, max_confidence, status,
                   work_order, batch_id
            FROM records WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["detections"] = json.loads(data.pop("detections_json") or "[]")
        try:
            data["labels"] = json.loads(data.pop("labels_json") or "{}")
        except json.JSONDecodeError:
            data["labels"] = {}
            data.pop("labels_json", None)
        return data
    finally:
        conn.close()


def delete_record(record_id: int, settings: Settings | None = None) -> bool:
    init_db(settings)
    conn = connect(settings)
    try:
        cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_many(ids: list[int], settings: Settings | None = None) -> int:
    if not ids:
        return 0
    init_db(settings)
    conn = connect(settings)
    try:
        q = ",".join("?" for _ in ids)
        cur = conn.execute(f"DELETE FROM records WHERE id IN ({q})", list(ids))
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def clear_all_records(settings: Settings | None = None) -> int:
    init_db(settings)
    conn = connect(settings)
    try:
        cur = conn.execute("DELETE FROM records")
        conn.commit()
        return int(cur.rowcount)
    finally:
        conn.close()


def list_image_paths_by_ids(ids: list[int], settings: Settings | None = None) -> list[str]:
    if not ids:
        return []
    init_db(settings)
    conn = connect(settings)
    try:
        q = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT image_path FROM records WHERE id IN ({q})", list(ids)
        ).fetchall()
        return [r["image_path"] for r in rows if r["image_path"]]
    finally:
        conn.close()


def list_all_image_paths(settings: Settings | None = None) -> list[str]:
    init_db(settings)
    conn = connect(settings)
    try:
        rows = conn.execute(
            "SELECT image_path FROM records WHERE image_path IS NOT NULL"
        ).fetchall()
        return [r["image_path"] for r in rows if r["image_path"]]
    finally:
        conn.close()


def count_records(settings: Settings | None = None) -> int:
    init_db(settings)
    conn = connect(settings)
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()
        return int(row["c"] if row else 0)
    finally:
        conn.close()


def stats(settings: Settings | None = None) -> dict[str, Any]:
    init_db(settings)
    conn = connect(settings)
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
        det_sum = conn.execute(
            "SELECT COALESCE(SUM(num_detections), 0) AS s FROM records"
        ).fetchone()["s"]
        rows = conn.execute(
            "SELECT source, COUNT(*) AS c FROM records GROUP BY source"
        ).fetchall()
        by_source = {str(r["source"]): int(r["c"]) for r in rows}

        # aggregate labels from labels_json
        by_label: dict[str, int] = {}
        for r in conn.execute(
            "SELECT labels_json FROM records WHERE labels_json IS NOT NULL"
        ).fetchall():
            try:
                lab = json.loads(r["labels_json"] or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(lab, dict):
                for k, v in lab.items():
                    try:
                        by_label[str(k)] = by_label.get(str(k), 0) + int(v)
                    except (TypeError, ValueError):
                        by_label[str(k)] = by_label.get(str(k), 0) + 1

        avg_elapsed = conn.execute(
            "SELECT AVG(elapsed_ms) AS a FROM records WHERE elapsed_ms IS NOT NULL"
        ).fetchone()["a"]
        alert_n = conn.execute(
            "SELECT COUNT(*) AS c FROM records WHERE status = 'alert'"
        ).fetchone()["c"]

        return {
            "total_records": int(total),
            "total_detections": int(det_sum),
            "by_source": by_source,
            "by_label": dict(sorted(by_label.items(), key=lambda kv: -kv[1])[:20]),
            "avg_elapsed_ms": round(float(avg_elapsed), 1) if avg_elapsed is not None else None,
            "alert_records": int(alert_n),
        }
    finally:
        conn.close()
