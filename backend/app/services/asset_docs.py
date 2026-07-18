"""Turn a Customer/Asset into the three representations the stores need:
  - embedding text (for Chroma vectors)
  - an Elasticsearch document (exact + fuzzy fields)
  - Chroma metadata (scalar values only)
"""

from __future__ import annotations

from typing import Dict, List

from ..models import Asset, Customer
from .normalize import derived_fields


def asset_keywords(asset: Asset) -> List[str]:
    kws = {asset.value, *asset.aliases, *asset.keywords}
    return [k for k in kws if k]


def asset_embedding_text(customer: Customer, asset: Asset) -> str:
    concerns = ", ".join(
        c.type.value + (f" ({c.note})" if c.note else "") for c in asset.concerns
    )
    parts = [
        f"{customer.name} — {customer.type.value}",
        f"{asset.type.value}: {asset.value}",
    ]
    if asset.aliases:
        parts.append("aka " + ", ".join(asset.aliases))
    if concerns:
        parts.append("concerns: " + concerns)
    if customer.protect_summary:
        parts.append(customer.protect_summary)
    return " | ".join(parts)


def asset_es_doc(customer: Customer, asset: Asset) -> Dict:
    d = derived_fields(asset)
    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "asset_id": asset.id,
        "asset_type": asset.type.value,
        "value": asset.value,
        "aliases": asset.aliases,
        "domain": d["domain"],
        "handle": d["handle"],
        "brand": d["brand"],
        "executive": d["executive"],
        "keywords": asset_keywords(asset),
        "concerns": [c.type.value for c in asset.concerns],
    }


def asset_chroma_metadata(customer: Customer, asset: Asset) -> Dict:
    # Chroma metadata values must be scalar (str/int/float/bool) — no lists.
    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_type": customer.type.value,
        "asset_id": asset.id,
        "asset_type": asset.type.value,
        "asset_value": asset.value,
        "concerns": ",".join(c.type.value for c in asset.concerns),
    }
