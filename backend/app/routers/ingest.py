"""Part-1 ingestion endpoints (SSE progress stream + status + reset)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..db.chroma_client import ChromaAssets
from ..db.es_client import ESAssets
from ..services.catalog import all_customers, get_customer
from ..services.ingest import (
    STATE,
    ingest_all_sync,
    ingest_customer_events,
    reset_stores,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/status")
def status() -> dict:
    return {
        "ingested_customer_ids": STATE.all(),
        "total_customers": len(all_customers()),
        "es_assets": ESAssets().count(),
        "chroma_vectors": ChromaAssets().count(),
    }


@router.get("/{customer_id}/stream")
def stream(customer_id: str) -> StreamingResponse:
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")

    def gen():
        for event in ingest_customer_events(customer):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/all")
def ingest_all() -> dict:
    """Ingest every customer at once (bulk, no streaming)."""
    return ingest_all_sync()


@router.post("/reset")
def reset() -> dict:
    return reset_stores()
