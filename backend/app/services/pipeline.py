"""Step-through Part-2 pipeline runs (for the pause/play/replay UI).

A run holds intermediate state; `step_run` executes one stage at a time and records that
stage's input and output so the UI can inspect each component. Stages:
  enrich → vector_match → string_match → dedup → classify
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional

from ..config import settings
from ..db.metrics_db import record_stage
from ..models import ContentItem
from .catalog import get_content
from .enrichment_agent import aenrich_content
from .matcher import (
    VECTOR_THRESHOLD,
    VECTOR_TOP_N,
    build_query_text,
    extract_terms,
    merge_matches,
    string_match,
    vector_match,
)
from .threat_agent import aclassify

STAGE_NAMES = ["enrich", "vector_match", "string_match", "dedup", "classify"]


def _mini(h: dict) -> dict:
    return {
        "asset_id": h["asset_id"],
        "customer_name": h["customer_name"],
        "asset_type": h["asset_type"],
        "asset_value": h["asset_value"],
        "score": round(h.get("score") or 0.0, 3),
        "source": h.get("source"),
    }


class Stage:
    def __init__(self, name: str):
        self.name = name
        self.status = "pending"  # pending | running | done | error
        self.input: Optional[dict] = None
        self.output: Optional[dict] = None
        self.duration_ms: Optional[int] = None
        self.meta: Optional[dict] = None  # extra info, e.g. per-company classify timings

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "meta": self.meta,
        }


class Run:
    def __init__(self, item: ContentItem):
        self.run_id = uuid.uuid4().hex[:12]
        self.item = item
        self.stages = [Stage(n) for n in STAGE_NAMES]
        self.cursor = 0
        # intermediates
        self.enrichment = None
        self.vec: Dict[str, dict] = {}
        self.exact: Dict[str, dict] = {}
        self.fuzzy: Dict[str, dict] = {}
        self.matches: list = []
        self.threat = None

    def content_dict(self) -> dict:
        return {
            "id": self.item.id,
            "type": self.item.type.value,
            "label": self.item.label,
            "text": self.item.text,
            "image_path": self.item.image_path,
            "has_image": bool(self.item.image_path),
        }

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "content_id": self.item.id,
            "content": self.content_dict(),
            "stages": [s.to_dict() for s in self.stages],
            "cursor": self.cursor,
            "done": self.cursor >= len(self.stages),
        }


RUNS: Dict[str, Run] = {}


def _compute_input(run: "Run", name: str) -> Optional[dict]:
    """A stage's input, derived from run state — so the UI can show it before the stage runs."""
    if name == "enrich":
        return {"type": run.item.type.value, "text": run.item.text, "image_path": run.item.image_path}
    if name == "vector_match":
        return {
            "query_text": build_query_text(run.item, run.enrichment),
            "top_n": VECTOR_TOP_N,
            "threshold": VECTOR_THRESHOLD,
        }
    if name == "string_match":
        return extract_terms(run.enrichment)
    if name == "dedup":
        return {"vector": len(run.vec), "exact": len(run.exact), "fuzzy": len(run.fuzzy)}
    if name == "classify":
        return {"candidate_assets": len(run.matches)}
    return None


def start_run(content_id: str) -> Run:
    item = get_content(content_id)
    if not item:
        raise KeyError(content_id)
    run = Run(item)
    run.stages[0].input = _compute_input(run, run.stages[0].name)  # enrich input ready up front
    RUNS[run.run_id] = run
    # keep the store bounded
    if len(RUNS) > 50:
        for stale in list(RUNS)[:-50]:
            RUNS.pop(stale, None)
    return run


def get_run(run_id: str) -> Optional[Run]:
    return RUNS.get(run_id)


async def step_run(run: Run) -> Run:
    if run.cursor >= len(run.stages):
        return run
    stage = run.stages[run.cursor]
    stage.status = "running"
    if stage.input is None:
        stage.input = _compute_input(run, stage.name)
    t0 = time.perf_counter()
    model: Optional[str] = None
    try:
        if stage.name == "enrich":
            model = settings.claude_enrichment_model
            run.enrichment = await aenrich_content(run.item)
            stage.output = run.enrichment.model_dump()
        elif stage.name == "vector_match":
            model = settings.openai_embedding_model
            run.vec = vector_match(run.item, run.enrichment)
            stage.output = {"candidates": [_mini(h) for h in run.vec.values()]}
        elif stage.name == "string_match":
            run.exact, run.fuzzy = string_match(run.enrichment)
            stage.output = {
                "exact": [_mini(h) for h in run.exact.values()],
                "fuzzy": [_mini(h) for h in run.fuzzy.values()],
            }
        elif stage.name == "dedup":
            run.matches = merge_matches(run.vec, run.exact, run.fuzzy)
            stage.output = {"matches": [m.model_dump() for m in run.matches]}
        elif stage.name == "classify":
            model = settings.claude_threat_model
            timing: dict = {}
            run.threat = await aclassify(run.item, run.enrichment, run.matches, timing_out=timing)
            stage.output = run.threat.model_dump()
            stage.meta = timing
        stage.status = "done"
    except Exception as exc:  # noqa: BLE001 - surface stage failures to the UI
        stage.status = "error"
        stage.output = {"error": str(exc)}
    stage.duration_ms = round((time.perf_counter() - t0) * 1000)
    record_stage(run.run_id, run.item.id, stage.name, stage.duration_ms, model=model, meta=stage.meta)
    run.cursor += 1
    # Pre-compute the NEXT stage's input so the UI can show it the instant you switch to it.
    if run.cursor < len(run.stages):
        try:
            nxt = run.stages[run.cursor]
            nxt.input = _compute_input(run, nxt.name)
        except Exception:  # noqa: BLE001
            pass
    return run
