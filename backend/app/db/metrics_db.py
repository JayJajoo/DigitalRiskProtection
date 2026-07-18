"""SQLite metrics store for pipeline stage timings (a separate `metrics.db`)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data"  # backend/data
DB_PATH = DATA_DIR / "metrics.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stage_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    content_id TEXT,
    stage TEXT,
    duration_ms INTEGER,
    model TEXT,
    meta TEXT,
    created_at REAL
)
"""


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(_SCHEMA)
    return conn


def record_stage(
    run_id: str,
    content_id: str,
    stage: str,
    duration_ms: int,
    model: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    """Persist one stage timing. Never raises (metrics must not break the pipeline)."""
    try:
        conn = _connect()
        conn.execute(
            "INSERT INTO stage_metrics (run_id, content_id, stage, duration_ms, model, meta, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, content_id, stage, int(duration_ms), model,
             json.dumps(meta) if meta else None, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def summary(recent_limit: int = 200) -> dict:
    try:
        conn = _connect()
        per_stage = [
            {"stage": r[0], "count": r[1], "avg_ms": round(r[2] or 0), "max_ms": r[3]}
            for r in conn.execute(
                "SELECT stage, COUNT(*), AVG(duration_ms), MAX(duration_ms)"
                " FROM stage_metrics GROUP BY stage"
            ).fetchall()
        ]
        recent = [
            {"run_id": r[0], "content_id": r[1], "stage": r[2], "duration_ms": r[3],
             "model": r[4], "at": r[5]}
            for r in conn.execute(
                "SELECT run_id, content_id, stage, duration_ms, model, created_at"
                " FROM stage_metrics ORDER BY id DESC LIMIT ?",
                (recent_limit,),
            ).fetchall()
        ]
        total = conn.execute("SELECT COUNT(*) FROM stage_metrics").fetchone()[0]
        conn.close()
        return {"total_records": total, "per_stage": per_stage, "recent": recent}
    except Exception:  # noqa: BLE001
        return {"total_records": 0, "per_stage": [], "recent": []}
