"""Enrichment output schema produced by the Claude Sonnet agent (PROJECT.md §7.1)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .enums import ContentType, Sentiment


class Entities(BaseModel):
    persons: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    handles: List[str] = Field(default_factory=list)  # @handles / emails / domains
    keywords: List[str] = Field(default_factory=list)


class Weapons(BaseModel):
    knife: bool = False
    gun: bool = False
    other: List[str] = Field(default_factory=list)


class ImageAnalysis(BaseModel):
    person_present: bool = False
    num_persons: int = 0
    weapons: Weapons = Field(default_factory=Weapons)
    dangerous_objects: List[str] = Field(default_factory=list)
    money_signs: bool = False  # cash / "money-flipping" visual cues
    scene_description: str = ""
    objects: List[str] = Field(default_factory=list)
    brands_logos: List[str] = Field(default_factory=list)
    text_in_image: str = ""


class RiskSignals(BaseModel):
    threat_language: bool = False
    violence_indicator: bool = False
    physical_threat: bool = False
    money_flipping: bool = False
    spam: bool = False
    phishing: bool = False
    scam: bool = False
    impersonation: bool = False
    doxxing_pii_exposure: bool = False
    credential_or_data_leak: bool = False
    hate_or_harassment: bool = False


class TargetsMentioned(BaseModel):
    persons: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)  # emails / domains / handles referenced


class EnrichmentResult(BaseModel):
    content_id: str
    content_type: ContentType
    summary: str = ""
    languages: List[str] = Field(default_factory=list)
    detected_text: str = ""  # OCR/transcribed text from an image
    entities: Entities = Field(default_factory=Entities)
    image_analysis: Optional[ImageAnalysis] = None  # null when no image
    risk_signals: RiskSignals = Field(default_factory=RiskSignals)
    targets_mentioned: TargetsMentioned = Field(default_factory=TargetsMentioned)
    sentiment: Sentiment = Sentiment.neutral
    toxicity_score: float = 0.0
    confidence: float = 0.0
