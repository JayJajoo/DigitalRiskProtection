"""Metrics endpoint — aggregate pipeline stage timings from the SQLite metrics DB."""

from __future__ import annotations

from fastapi import APIRouter

from ..db.metrics_db import summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
def get_summary() -> dict:
    return summary()
