"""Content corpus endpoints + enrichment (Phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from ..models import EnrichmentResult
from ..services.catalog import all_content, get_content
from ..services.data_loader import image_path
from ..services.enrichment_agent import aenrich_content
from ..services.matcher import match_content
from ..services.threat_agent import aclassify

router = APIRouter(prefix="/content", tags=["content"])


@router.get("")
def list_content() -> list[dict]:
    out = []
    for item in all_content():
        text = item.text or ""
        out.append(
            {
                "id": item.id,
                "type": item.type.value,
                "origin": item.origin.value,
                "label": item.label,
                "targets_hint": item.targets_hint,
                "has_image": bool(item.image_path),
                "text_preview": text[:140] + ("…" if len(text) > 140 else ""),
            }
        )
    return out


@router.get("/{content_id}")
def get_one(content_id: str) -> dict:
    item = get_content(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="content not found")
    return item.model_dump()


@router.get("/{content_id}/image")
def content_image(content_id: str):
    item = get_content(content_id)
    if not item or not item.image_path:
        raise HTTPException(status_code=404, detail="no image for this content")
    path = image_path(item.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="image file missing")
    return FileResponse(str(path))


@router.post("/{content_id}/enrich", response_model=EnrichmentResult)
async def enrich(content_id: str) -> EnrichmentResult:
    item = get_content(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="content not found")
    try:
        return await aenrich_content(item)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"enrichment failed: {exc}") from exc


@router.post("/{content_id}/match")
async def match(content_id: str) -> dict:
    """Enrich a content item, then match it against the ingested assets."""
    item = get_content(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="content not found")
    enrichment = await aenrich_content(item)
    matches = await run_in_threadpool(match_content, item, enrichment)
    return {
        "content_id": content_id,
        "enrichment": enrichment.model_dump(),
        "matches": [m.model_dump() for m in matches],
    }


@router.post("/{content_id}/analyze")
async def analyze(content_id: str) -> dict:
    """Full Part-2 chain for one item: enrich → match → per-asset threat classification."""
    item = get_content(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="content not found")
    enrichment = await aenrich_content(item)
    matches = await run_in_threadpool(match_content, item, enrichment)
    threat = await aclassify(item, enrichment, matches)
    return {
        "content_id": content_id,
        "enrichment": enrichment.model_dump(),
        "matches": [m.model_dump() for m in matches],
        "threat": threat.model_dump(),
    }
