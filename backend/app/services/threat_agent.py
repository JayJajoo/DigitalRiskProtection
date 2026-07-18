"""Per-asset threat classification via the Claude Agent SDK (Opus).

Given a content item, its enrichment, and the candidate assets from the matcher, one Opus call
returns a verdict per asset (is_threat / severity / threat_type / reason). Matcher fields
(asset value, customer, provenance, score) and the per-company rollup are filled deterministically.
"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional

from claude_agent_sdk import ClaudeAgentOptions

from ..config import settings
from ..models import (
    AssetMatch,
    AssetVerdict,
    CompanyRollup,
    ContentItem,
    EnrichmentResult,
    Severity,
    ThreatResult,
)
from .agent_common import extract_json, run_query

SEV_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}

SYSTEM_PROMPT = """You are a Digital Risk Protection threat analyst. You receive a piece of online
content, its structured enrichment, and a list of CANDIDATE protected assets a matcher linked to
it. For EACH candidate asset decide whether this content is a real risk to THAT specific asset/customer.

Return ONLY JSON:
{"verdicts":[{"asset_id":"...","is_threat":true,"severity":"none|low|medium|high","threat_type":"physical|reputational|financial|data-leak|scam|phishing|impersonation|other","reason":"one grounded sentence","recommended_action":"short action","confidence":0.0}]}

Guidance:
- is_threat=true ONLY if the content genuinely targets or harms this asset or its owner. If an
  asset merely matched coincidentally (e.g. a benign message that only fuzzy-matched a name or a
  common word), return is_threat=false and severity="none".
- severity: physical-safety/doxxing and credible account-takeover phishing rank higher; vague
  mentions are low. Non-threats are "none".
- Give one specific reason per asset. confidence is 0..1. Output valid JSON only."""


def _candidate_block(matches: List[AssetMatch]) -> str:
    return "\n".join(
        f"- asset_id={m.asset_id} | customer={m.customer_name} | {m.asset_type.value}={m.asset_value}"
        f" | matched_by={'+'.join(s.value for s in m.matched_by)} score={m.match_score}"
        for m in matches
    )


def _build_prompt(item: ContentItem, enr: EnrichmentResult, matches: List[AssetMatch]) -> str:
    risks = [k for k, v in enr.risk_signals.model_dump().items() if v]
    img = ""
    if enr.image_analysis:
        ia = enr.image_analysis
        img = (
            f"\nIMAGE: person_present={ia.person_present}, weapons={ia.weapons.model_dump()}, "
            f"money_signs={ia.money_signs}, objects={ia.objects}, scene={ia.scene_description}"
        )
    return f"""CONTENT (id={item.id}, type={item.type.value}):
{item.text or '(image only)'}

ENRICHMENT:
summary: {enr.summary}
risk_signals(true): {risks}
sentiment: {enr.sentiment.value} | toxicity: {enr.toxicity_score}
entities.persons: {enr.entities.persons}
entities.organizations: {enr.entities.organizations}
targets.assets: {enr.targets_mentioned.assets}{img}

CANDIDATE ASSETS:
{_candidate_block(matches)}

Return one verdict per candidate asset_id above. JSON only."""


def _rollup(verdicts: List[AssetVerdict]) -> List[CompanyRollup]:
    by_cust: Dict[str, dict] = {}
    for v in verdicts:
        c = by_cust.setdefault(v.customer_id, {"name": v.customer_name, "verdicts": []})
        c["verdicts"].append(v)

    out: List[CompanyRollup] = []
    for cid, info in by_cust.items():
        threats = [v for v in info["verdicts"] if v.is_threat]
        if threats:
            top = max(threats, key=lambda v: SEV_ORDER[v.severity.value])
            max_sev, summary = top.severity.value, top.reason
        else:
            max_sev, summary = "none", "No credible threat to this customer's assets."
        out.append(
            CompanyRollup(
                customer_id=cid,
                customer_name=info["name"],
                max_severity=Severity(max_sev),
                threat_asset_count=len(threats),
                summary=summary,
            )
        )
    out.sort(key=lambda r: SEV_ORDER[r.max_severity.value], reverse=True)
    return out


def _options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=settings.claude_threat_model,
        fallback_model="opus",
        allowed_tools=[],
        permission_mode="bypassPermissions",
        max_turns=2,
    )


def _verdict_from(m: AssetMatch, v: dict) -> AssetVerdict:
    sev = str(v.get("severity", "none")).lower()
    if sev not in SEV_ORDER:
        sev = "none"
    is_threat = bool(v.get("is_threat", False))
    return AssetVerdict(
        asset_id=m.asset_id,
        asset_type=m.asset_type,
        asset_value=m.asset_value,
        customer_id=m.customer_id,
        customer_name=m.customer_name,
        matched_by=m.matched_by,
        match_score=m.match_score,
        is_threat=is_threat,
        severity=Severity(sev if is_threat else "none"),
        threat_type=v.get("threat_type"),
        reason=v.get("reason", ""),
        recommended_action=v.get("recommended_action", ""),
        confidence=float(v.get("confidence", 0.0) or 0.0),
    )


def _heuristic_verdict(m: AssetMatch, enr: EnrichmentResult) -> dict:
    """Deterministic rule-based verdict for when the Opus call fails (moderation/transient),
    so a genuinely-matched threat isn't silently dropped."""
    rs = enr.risk_signals
    high = (
        rs.physical_threat or rs.violence_indicator or rs.credential_or_data_leak
        or rs.doxxing_pii_exposure
    )
    med = (
        rs.phishing or rs.scam or rs.impersonation or rs.money_flipping
        or rs.threat_language or rs.hate_or_harassment
    )
    strong = any(s.value == "exact" for s in m.matched_by) or m.match_score >= 0.75
    if not (high or med) or not strong:
        return {"is_threat": False, "severity": "none", "reason": "", "confidence": 0.2}
    ttype = (
        "data-leak" if rs.credential_or_data_leak
        else "physical" if (rs.physical_threat or rs.violence_indicator)
        else "phishing" if rs.phishing
        else "scam"
    )
    active = [k for k, v in rs.model_dump().items() if v]
    return {
        "is_threat": True,
        "severity": "high" if high else "medium",
        "threat_type": ttype,
        "reason": f"(LLM unavailable) rule-based flag: strong match on this asset + risk signals {active}.",
        "recommended_action": "manual review",
        "confidence": 0.4,
    }


async def _classify_group(
    item: ContentItem, enr: EnrichmentResult, group: List[AssetMatch]
) -> tuple[str, int, Dict[str, dict]]:
    """One Opus call for a single customer's assets → (customer_name, duration_ms, {asset_id: verdict})."""
    t0 = time.perf_counter()
    try:
        text = await run_query(_build_prompt(item, enr, group), _options())
        data = extract_json(text)
        verdicts = {v.get("asset_id"): v for v in data.get("verdicts", [])}
    except Exception:  # noqa: BLE001 - fall back to rule-based verdicts for this group
        verdicts = {m.asset_id: _heuristic_verdict(m, enr) for m in group}
    ms = round((time.perf_counter() - t0) * 1000)
    return (group[0].customer_name, ms, verdicts)


async def aclassify(
    item: ContentItem,
    enr: EnrichmentResult,
    matches: List[AssetMatch],
    timing_out: Optional[dict] = None,
) -> ThreatResult:
    if not matches:
        return ThreatResult(content_id=item.id, asset_verdicts=[], company_rollup=[])

    # One Opus call PER matched customer (grouping that customer's assets) — keeps asset-level
    # nuance within a customer while isolating customers from each other. Calls run concurrently.
    groups: Dict[str, List[AssetMatch]] = {}
    for m in matches:
        groups.setdefault(m.customer_id, []).append(m)

    results = await asyncio.gather(
        *(_classify_group(item, enr, g) for g in groups.values())
    )
    by_id: Dict[str, dict] = {}
    per_company: List[dict] = []
    for cname, ms, verdicts in results:
        by_id.update(verdicts)
        per_company.append({"customer_name": cname, "ms": ms})

    if timing_out is not None:
        per_company.sort(key=lambda p: p["ms"], reverse=True)
        timing_out["companies"] = len(per_company)
        timing_out["per_company"] = per_company
        timing_out["avg_company_ms"] = (
            round(sum(p["ms"] for p in per_company) / len(per_company)) if per_company else 0
        )
        timing_out["total_llm_ms"] = sum(p["ms"] for p in per_company)

    verdicts = [_verdict_from(m, by_id.get(m.asset_id, {})) for m in matches]
    return ThreatResult(
        content_id=item.id,
        asset_verdicts=verdicts,
        company_rollup=_rollup(verdicts),
    )


def classify(item: ContentItem, enr: EnrichmentResult, matches: List[AssetMatch]) -> ThreatResult:
    return asyncio.run(aclassify(item, enr, matches))
