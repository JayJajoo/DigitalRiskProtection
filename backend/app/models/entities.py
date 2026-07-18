"""Core data-lake models: Customer, Asset, Concern, ContentItem.

These back the Part-1 profiles (`backend/data/profiles/*.json`) and the Part-2 content
corpus (`backend/data/corpus/`). See PROJECT.md §4.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from .enums import (
    AssetType,
    ConcernType,
    ContentOrigin,
    ContentType,
    CustomerType,
)


class Concern(BaseModel):
    """An attack type an asset should be protected against."""

    type: ConcernType
    note: Optional[str] = None


class Asset(BaseModel):
    id: str
    type: AssetType
    value: str
    aliases: List[str] = Field(default_factory=list)
    concerns: List[Concern] = Field(default_factory=list)
    # Optional pre-computed search helpers; if omitted they are derived at index time.
    keywords: List[str] = Field(default_factory=list)


class Customer(BaseModel):
    id: str
    name: str
    type: CustomerType
    description: str = ""
    industry: Optional[str] = None
    # "What they are / what they want to protect" — free text shown in the UI.
    protect_summary: str = ""
    assets: List[Asset] = Field(default_factory=list)


class ContentItem(BaseModel):
    id: str
    source: str = "synthetic-corpus"
    origin: ContentOrigin = ContentOrigin.synthetic
    type: ContentType = ContentType.text
    text: Optional[str] = None
    image_path: Optional[str] = None
    # Ground-truth hint for the demo (e.g. "phishing", "benign"); not used by the pipeline.
    label: Optional[str] = None
    # Free-form note on which entity/asset this item was authored to touch.
    targets_hint: Optional[str] = None
