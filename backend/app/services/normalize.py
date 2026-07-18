"""Normalization helpers for asset values and match keys.

Shared by ingestion (Phase 3) and the matcher (Phase 5) so both sides derive the same
canonical forms (strip `@`, lowercase, extract root domains).
"""

from __future__ import annotations

import re
from typing import Dict

from ..models import Asset


def strip_handle(value: str) -> str:
    """'@NovaBank_Support' -> 'novabank_support'."""
    return value.strip().lstrip("@").lower()


def extract_domain(value: str) -> str:
    """Get a root-ish domain from an email or URL.

    'support@Novabank.example' -> 'novabank.example'
    'https://www.jayjajoo.github.com/portfolio-v2' -> 'jayjajoo.github.com'
    """
    v = value.strip().lower()
    if "@" in v and " " not in v:  # email
        return v.split("@")[-1]
    v = re.sub(r"^[a-z]+://", "", v)  # strip scheme
    v = v.split("/")[0]  # netloc only
    v = re.sub(r"^www\.", "", v)
    return v


def derived_fields(asset: Asset) -> Dict[str, str]:
    """Populate the ES search-helper fields based on the asset's type."""
    t = asset.type.value
    value = asset.value
    fields = {"domain": "", "handle": "", "brand": "", "executive": ""}
    if t in ("domain", "website", "email"):
        fields["domain"] = extract_domain(value)
    if t == "social_handle":
        fields["handle"] = strip_handle(value)
    if t == "brand":
        fields["brand"] = value
    if t == "executive":
        fields["executive"] = value
    return fields
