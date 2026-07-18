"""Pydantic domain models for the DRP pipeline (PROJECT.md §4 & §7)."""

from .enums import (
    AssetType,
    ConcernType,
    ContentOrigin,
    ContentType,
    CustomerType,
    MatchSource,
    Sentiment,
    Severity,
)
from .entities import Asset, Concern, ContentItem, Customer
from .enrichment import (
    Entities,
    EnrichmentResult,
    ImageAnalysis,
    RiskSignals,
    TargetsMentioned,
    Weapons,
)
from .verdict import AssetMatch, AssetVerdict, CompanyRollup, ThreatResult

__all__ = [
    # enums
    "AssetType",
    "ConcernType",
    "ContentOrigin",
    "ContentType",
    "CustomerType",
    "MatchSource",
    "Sentiment",
    "Severity",
    # entities
    "Asset",
    "Concern",
    "ContentItem",
    "Customer",
    # enrichment
    "Entities",
    "EnrichmentResult",
    "ImageAnalysis",
    "RiskSignals",
    "TargetsMentioned",
    "Weapons",
    # verdict
    "AssetMatch",
    "AssetVerdict",
    "CompanyRollup",
    "ThreatResult",
]
