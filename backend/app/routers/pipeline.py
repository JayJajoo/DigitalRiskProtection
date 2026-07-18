"""Step-through Part-2 pipeline endpoints (for the pause/play/replay UI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services.pipeline import get_run, start_run, step_run

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/start")
def start(content_id: str) -> dict:
    try:
        return start_run(content_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="content not found") from exc


@router.get("/{run_id}")
def get(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run.to_dict()


@router.post("/{run_id}/step")
async def step(run_id: str) -> dict:
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    await step_run(run)
    return run.to_dict()
