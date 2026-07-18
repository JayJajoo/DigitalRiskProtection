"""Matching + threat-classification models (PROJECT.md §7.2).

The classifier produces one verdict PER matched asset, then a per-company rollup.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .enums import AssetType, MatchSource, Severity


class AssetMatch(BaseModel):
    """A candidate asset surfaced by the matcher (pre-classification)."""

    asset_id: str
    asset_type: AssetType
    asset_value: str
    customer_id: str
    customer_name: str
    matched_by: List[MatchSource] = Field(default_factory=list)
    match_score: float = 0.0
    matched_fields: List[str] = Field(default_factory=list)  # which ES fields/clauses hit


class AssetVerdict(BaseModel):
    asset_id: str
    asset_type: AssetType
    asset_value: str
    customer_id: str
    customer_name: str
    matched_by: List[MatchSource] = Field(default_factory=list)
    match_score: float = 0.0
    is_threat: bool = False
    severity: Severity = Severity.none
    threat_type: Optional[str] = None
    reason: str = ""
    recommended_action: str = ""
    confidence: float = 0.0


class CompanyRollup(BaseModel):
    customer_id: str
    customer_name: str
    max_severity: Severity = Severity.none
    threat_asset_count: int = 0
    summary: str = ""


class ThreatResult(BaseModel):
    content_id: str
    asset_verdicts: List[AssetVerdict] = Field(default_factory=list)
    company_rollup: List[CompanyRollup] = Field(default_factory=list)
