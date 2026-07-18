"""Health / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict:
    """Liveness check plus a summary of which integrations are configured.

    In Phase 0 this does not probe Elasticsearch/Chroma (clients are added in Phase 2);
    it reports whether required credentials/URLs are present so the UI can surface setup gaps.
    """
    return {
        "status": "ok",
        "service": "drp-backend",
        "version": __version__,
        "config": {
            "openai_configured": settings.openai_configured,
            "anthropic_configured": settings.anthropic_configured,
            "elasticsearch_url": settings.elasticsearch_url,
            "chroma_persist_dir": settings.chroma_persist_dir,
        },
    }
