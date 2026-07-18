"""Content enrichment via the Claude Agent SDK (Sonnet).

Produces the EnrichmentResult JSON (PROJECT.md §7.1) for a content item. For image items the
agent uses the Read tool to view the image file and fill `image_analysis`.

Auth: the Agent SDK runs on the Claude Code CLI, so this uses your Claude Code login (or
ANTHROPIC_API_KEY). The `claude` CLI must be on PATH at runtime.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Optional

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from ..config import settings
from ..models import (
    ContentItem,
    EnrichmentResult,
    Entities,
    RiskSignals,
    TargetsMentioned,
)
from .data_loader import DATA_DIR, image_path

SCHEMA_HINT = """{
  "summary": "1-2 sentence summary of the content",
  "languages": ["ISO codes of languages present, e.g. en, es, hi"],
  "detected_text": "text transcribed/OCR'd from an image, else empty",
  "entities": {
    "persons": [], "organizations": [], "locations": [],
    "handles": ["@handles, emails, domains found — see de-obfuscation rule"],
    "keywords": ["salient terms"]
  },
  "image_analysis": {
    "person_present": false, "num_persons": 0,
    "weapons": {"knife": false, "gun": false, "other": []},
    "dangerous_objects": [], "money_signs": false,
    "scene_description": "", "objects": [], "brands_logos": [], "text_in_image": ""
  },
  "risk_signals": {
    "threat_language": false, "violence_indicator": false, "physical_threat": false,
    "money_flipping": false, "spam": false, "phishing": false, "scam": false,
    "impersonation": false, "doxxing_pii_exposure": false,
    "credential_or_data_leak": false, "hate_or_harassment": false
  },
  "targets_mentioned": {"persons": [], "organizations": [], "assets": ["emails/domains/handles the content targets"]},
  "sentiment": "negative | neutral | positive",
  "toxicity_score": 0.0,
  "confidence": 0.0
}"""

SYSTEM_PROMPT = f"""You are a Digital Risk Protection content-enrichment engine. Analyze the
given content (which may be a threat, scam, benign, or ambiguous) and extract structured signals.

Return ONLY one JSON object matching exactly this schema (no markdown fences, no prose):
{SCHEMA_HINT}

Rules:
- Judge INTENT, not just keywords. Veiled/coded threats, sarcasm, and politely-worded extortion
  should set the appropriate risk_signals; benign uses of alarming words (e.g. "kill the
  presentation", a chef's knife) must NOT.
- De-obfuscation: if a handle/email/domain is disguised with homoglyphs, leetspeak, or spacing
  (e.g. "n0vab4nk", "zеnpay" with a Cyrillic e, "j a y @ gmail . com"), ALSO include the plain
  normalized form in entities.handles and targets_mentioned.assets so downstream matching works.
- image_analysis must be null when there is no image.
- toxicity_score and confidence are 0..1. Keep JSON strictly valid."""


async def _run(prompt: str, options: ClaudeAgentOptions) -> str:
    chunks: list[str] = []
    result_text: Optional[str] = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    chunks.append(block.text)
        elif isinstance(msg, ResultMessage):
            result_text = getattr(msg, "result", None)
    return (result_text or "\n".join(chunks)).strip()


def _extract_json(text: str) -> dict:
    t = text.strip()
    if "```" in t:
        t = re.sub(r"```(json)?", "", t).strip()
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j != -1:
        t = t[i : j + 1]
    return json.loads(t)


def _build_prompt(item: ContentItem, image_abs: Optional[str]) -> str:
    parts = [f"CONTENT ITEM id={item.id}, type={item.type.value}."]
    if item.text:
        parts.append(f"TEXT:\n{item.text}")
    if image_abs:
        parts.append(
            f"An image is attached at: {image_abs}\n"
            "Use the Read tool to view it, then fill image_analysis based on what you actually see."
        )
    else:
        parts.append("No image — set image_analysis to null.")
    parts.append("Return only the JSON object.")
    return "\n\n".join(parts)


def _fallback_enrichment(item: ContentItem) -> EnrichmentResult:
    """Deterministic degraded enrichment for when the agent errors (moderation/transient) so the
    detection pipeline still runs. Extracts identifiers + risk keywords from the raw text; it does
    NOT reproduce the content — it only yields signals for matching + a threat alert."""
    text = item.text or ""
    handles = re.findall(r"@\w+", text)
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", text)
    domains = re.findall(r"\b[a-z0-9-]+\.(?:example|com|net|org|io|co)\b", text, re.I)
    names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
    orgs = re.findall(r"\b[A-Z][a-z]{3,}\b", text)
    low = text.lower()

    def has(*kw: str) -> bool:
        return any(k in low for k in kw)

    rs = RiskSignals(
        credential_or_data_leak=has("leak", "export", "card number", "account holder", "csv", "dump", "breach", "database", "records"),
        scam=has("selling", "priced", "for sale", "dm for", "per thousand", "double your"),
        phishing=has("verify", "log in", "login", "password", "reset your", "suspend"),
        doxxing_pii_exposure=has("home address", "lives at", "where you live", "st,"),
        physical_threat=has("kill", "hurt", "come for you", "watch your back"),
        threat_language=has("kill", "threat", "regret", "careful who you upset"),
    )
    uniq = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    active = any(rs.model_dump().values())
    return EnrichmentResult(
        content_id=item.id,
        content_type=item.type,
        summary="(enrichment agent unavailable for this content — degraded local extraction used)",
        languages=["en"],
        entities=Entities(
            persons=uniq(names),
            organizations=uniq(orgs),
            handles=uniq(handles + emails + domains),
            keywords=uniq(orgs + names),
        ),
        image_analysis=None,
        risk_signals=rs,
        targets_mentioned=TargetsMentioned(
            persons=uniq(names),
            organizations=uniq(orgs),
            assets=uniq(emails + domains),
        ),
        sentiment="negative" if active else "neutral",
        toxicity_score=0.4 if active else 0.0,
        confidence=0.2,
    )


async def aenrich_content(item: ContentItem) -> EnrichmentResult:
    image_abs: Optional[str] = None
    if item.image_path:
        p = image_path(item.image_path)
        if p.exists():
            image_abs = str(p)

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=settings.claude_enrichment_model,
        fallback_model="sonnet",
        allowed_tools=["Read"] if image_abs else [],
        permission_mode="bypassPermissions",
        max_turns=4,
        cwd=str(DATA_DIR),
    )
    prompt = _build_prompt(item, image_abs)

    # Retry once (transient), then fall back to deterministic extraction so a single agent
    # error (e.g. a moderation stop) never crashes the pipeline.
    for _ in range(2):
        try:
            text = await _run(prompt, options)
            data = _extract_json(text)
            data["content_id"] = item.id  # trust our own identifiers
            data["content_type"] = item.type.value
            if not image_abs:
                data["image_analysis"] = None
            return EnrichmentResult.model_validate(data)
        except Exception:  # noqa: BLE001
            continue
    return _fallback_enrichment(item)


def enrich_content(item: ContentItem) -> EnrichmentResult:
    """Sync wrapper for non-async callers (safe in threadpool contexts)."""
    return asyncio.run(aenrich_content(item))
