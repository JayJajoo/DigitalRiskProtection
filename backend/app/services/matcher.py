"""Match an enriched content item back to protected assets.

Two candidate sources (PROJECT.md §6):
  - vector similarity in Chroma (top-N above a threshold)
  - Elasticsearch string match — exact (`.keyword`) + fuzzy (`fuzziness: AUTO`)
…then merged and de-duplicated per asset, keeping `matched_by` provenance and a blended score.
"""

from __future__ import annotations

import json
from typing import Dict, List

from ..db.chroma_client import ChromaAssets
from ..db.es_client import ESAssets
from ..models import AssetMatch, AssetType, ContentItem, EnrichmentResult, MatchSource
from .embeddings import embed_texts
from .normalize import extract_domain, strip_handle

VECTOR_TOP_N = 10
VECTOR_THRESHOLD = 0.32  # cosine similarity floor
ES_SIZE = 15
TERM_CAP = 30
SOURCE_BASE = {"exact": 0.95, "fuzzy": 0.70}  # vector uses its actual cosine score


# ── query text for the vector search ────────────────────────────────
def build_query_text(item: ContentItem, enr: EnrichmentResult) -> str:
    parts: List[str] = []
    if item.text:
        parts.append(item.text)
    if enr.summary:
        parts.append(enr.summary)
    flat = {
        "persons": enr.entities.persons,
        "organizations": enr.entities.organizations,
        "handles": enr.entities.handles,
        "keywords": enr.entities.keywords,
        "targets": enr.targets_mentioned.assets,
        "risks": [k for k, v in enr.risk_signals.model_dump().items() if v],
    }
    parts.append(json.dumps(flat, ensure_ascii=False))
    if enr.image_analysis:
        if enr.image_analysis.scene_description:
            parts.append(enr.image_analysis.scene_description)
        if enr.image_analysis.objects:
            parts.append(", ".join(enr.image_analysis.objects))
    return "\n".join(p for p in parts if p)


# ── term helpers ────────────────────────────────────────────────────
def _looks_like_locator(v: str) -> bool:
    return ("@" in v) or ("://" in v) or ("." in v and " " not in v)


def _expand_id_term(v: str) -> set[str]:
    v = v.strip().lower()
    forms = {v}
    if _looks_like_locator(v):
        d = extract_domain(v)
        if d:
            forms.add(d)
    h = strip_handle(v)
    if h:
        forms.add(h)
    return {f for f in forms if len(f) >= 2}


def _terms(values: List[str], cap: int = TERM_CAP) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for v in values:
        v = (v or "").strip().lower()
        if v and v not in seen and len(v) >= 2:
            seen.add(v)
            out.append(v)
        if len(out) >= cap:
            break
    return out


# ── vector match ────────────────────────────────────────────────────
def vector_match(item: ContentItem, enr: EnrichmentResult) -> Dict[str, dict]:
    emb = embed_texts([build_query_text(item, enr)])[0]
    out: Dict[str, dict] = {}
    for h in ChromaAssets().query(emb, n_results=VECTOR_TOP_N):
        if h["score"] is None or h["score"] < VECTOR_THRESHOLD:
            continue
        m = h["metadata"]
        out[m["asset_id"]] = {
            "asset_id": m["asset_id"],
            "asset_type": m["asset_type"],
            "asset_value": m["asset_value"],
            "customer_id": m["customer_id"],
            "customer_name": m["customer_name"],
            "source": "vector",
            "score": h["score"],
        }
    return out


# ── string match (exact + fuzzy) ────────────────────────────────────
def _es_hits(records: List[dict], source: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for hit in records:
        s = hit["_source"]
        out[s["asset_id"]] = {
            "asset_id": s["asset_id"],
            "asset_type": s["asset_type"],
            "asset_value": s["value"],
            "customer_id": s["customer_id"],
            "customer_name": s["customer_name"],
            "source": source,
            "score": hit["_score"],
        }
    return out


def extract_terms(enr: EnrichmentResult) -> Dict[str, List[str]]:
    """The identity-bearing query terms pulled from the enrichment (see field map)."""
    id_terms: set[str] = set()
    for v in _terms(list(enr.entities.handles) + list(enr.targets_mentioned.assets)):
        id_terms |= _expand_id_term(v)
    if enr.image_analysis and enr.image_analysis.text_in_image:
        for tok in enr.image_analysis.text_in_image.lower().split():
            if _looks_like_locator(tok):
                id_terms |= _expand_id_term(tok)
    return {
        "id_terms": list(id_terms)[:TERM_CAP],
        "person_terms": _terms(list(enr.entities.persons) + list(enr.targets_mentioned.persons)),
        "org_terms": _terms(
            list(enr.entities.organizations)
            + list(enr.targets_mentioned.organizations)
            + (enr.image_analysis.brands_logos if enr.image_analysis else [])
        ),
        "kw_terms": _terms(enr.entities.keywords),
    }


def string_match(enr: EnrichmentResult):
    es = ESAssets()
    terms = extract_terms(enr)
    id_terms = terms["id_terms"]
    person_terms = terms["person_terms"]
    org_terms = terms["org_terms"]
    kw_terms = terms["kw_terms"]

    exact_should: List[dict] = []
    for t in id_terms:
        for f, b in (("value.keyword", 5), ("handle.keyword", 5), ("domain.keyword", 5), ("aliases.keyword", 3)):
            exact_should.append({"term": {f: {"value": t, "boost": b}}})
    for t in person_terms:
        for f, b in (("value.keyword", 4), ("executive.keyword", 4), ("aliases.keyword", 3), ("customer_name.keyword", 2)):
            exact_should.append({"term": {f: {"value": t, "boost": b}}})
    for t in org_terms:
        for f, b in (("brand.keyword", 4), ("customer_name.keyword", 3), ("value.keyword", 3)):
            exact_should.append({"term": {f: {"value": t, "boost": b}}})
    for t in kw_terms:
        exact_should.append({"term": {"keywords.keyword": {"value": t, "boost": 2}}})

    fuzzy_should: List[dict] = []
    for t in id_terms:
        fuzzy_should.append({"multi_match": {"query": t, "fields": ["value^2", "handle^2", "domain^2", "aliases"], "fuzziness": "AUTO"}})
    for t in person_terms:
        fuzzy_should.append({"multi_match": {"query": t, "fields": ["value", "aliases", "executive", "customer_name"], "fuzziness": "AUTO"}})
    for t in org_terms:
        fuzzy_should.append({"multi_match": {"query": t, "fields": ["brand^2", "customer_name", "value"], "fuzziness": "AUTO"}})

    exact_hits: Dict[str, dict] = {}
    fuzzy_hits: Dict[str, dict] = {}
    if exact_should:
        r = es.search({"bool": {"should": exact_should, "minimum_should_match": 1}}, size=ES_SIZE)
        exact_hits = _es_hits(r["hits"]["hits"], "exact")
    if fuzzy_should:
        r = es.search({"bool": {"should": fuzzy_should, "minimum_should_match": 1}}, size=ES_SIZE)
        fuzzy_hits = _es_hits(r["hits"]["hits"], "fuzzy")
    return exact_hits, fuzzy_hits


# ── merge + dedup ───────────────────────────────────────────────────
def merge_matches(vec: Dict[str, dict], exact: Dict[str, dict], fuzzy: Dict[str, dict]) -> List[AssetMatch]:
    merged: Dict[str, dict] = {}
    for hitmap in (vec, exact, fuzzy):
        for aid, h in hitmap.items():
            m = merged.setdefault(
                aid,
                {
                    "asset_id": h["asset_id"],
                    "asset_type": h["asset_type"],
                    "asset_value": h["asset_value"],
                    "customer_id": h["customer_id"],
                    "customer_name": h["customer_name"],
                    "sources": {},
                },
            )
            src = h["source"]
            score = h["score"] if src == "vector" else SOURCE_BASE[src]
            m["sources"][src] = max(m["sources"].get(src, 0.0), score or 0.0)

    results: List[AssetMatch] = []
    for m in merged.values():
        sources = m["sources"]
        results.append(
            AssetMatch(
                asset_id=m["asset_id"],
                asset_type=AssetType(m["asset_type"]),
                asset_value=m["asset_value"],
                customer_id=m["customer_id"],
                customer_name=m["customer_name"],
                matched_by=[MatchSource(s) for s in ("vector", "exact", "fuzzy") if s in sources],
                match_score=round(max(sources.values()) if sources else 0.0, 4),
                matched_fields=[f"{s}:{sources[s]:.2f}" for s in sources],
            )
        )
    results.sort(key=lambda r: r.match_score, reverse=True)
    return results


def match_content(item: ContentItem, enr: EnrichmentResult) -> List[AssetMatch]:
    vec = vector_match(item, enr)
    exact, fuzzy = string_match(enr)
    return merge_matches(vec, exact, fuzzy)
