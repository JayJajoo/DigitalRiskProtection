"""Store connectivity / status endpoint (Elasticsearch + Chroma + embeddings config)."""

from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..db.chroma_client import ChromaAssets
from ..db.es_client import ESAssets

router = APIRouter(prefix="/stores", tags=["stores"])


@router.get("/status")
def status() -> dict:
    es = ESAssets()
    es_up = es.ping()
    es_count = es.count() if es_up else 0

    chroma_up, chroma_count = True, 0
    try:
        chroma_count = ChromaAssets().count()
    except Exception:  # noqa: BLE001
        chroma_up = False

    return {
        "elasticsearch": {"up": es_up, "index": es.index, "assets_indexed": es_count},
        "chroma": {"up": chroma_up, "collection": "assets", "vectors": chroma_count},
        "embeddings": {
            "configured": settings.openai_configured,
            "model": settings.openai_embedding_model,
        },
    }
