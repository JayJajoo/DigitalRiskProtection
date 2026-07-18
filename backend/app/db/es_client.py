"""Elasticsearch wrapper for the asset index.

Every searchable string field is indexed as analyzed `text` (for fuzzy match) with a
`.keyword` sub-field (lowercased normalizer, for exact match) — see PROJECT.md §6 field map.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from elasticsearch import Elasticsearch, helpers

from ..config import settings

# Lowercasing normalizer so exact `.keyword` matches are case-insensitive.
ASSET_SETTINGS = {
    "analysis": {"normalizer": {"lc": {"type": "custom", "filter": ["lowercase"]}}}
}


def _text_kw() -> Dict:
    return {"type": "text", "fields": {"keyword": {"type": "keyword", "normalizer": "lc"}}}


ASSET_MAPPINGS = {
    "properties": {
        "customer_id": {"type": "keyword"},
        "customer_name": _text_kw(),
        "asset_id": {"type": "keyword"},
        "asset_type": {"type": "keyword"},
        "value": _text_kw(),
        "aliases": _text_kw(),
        "domain": _text_kw(),
        "handle": _text_kw(),
        "brand": _text_kw(),
        "executive": _text_kw(),
        "keywords": _text_kw(),
        "concerns": {"type": "keyword"},
    }
}


class ESAssets:
    def __init__(self, index: str = "assets", url: Optional[str] = None):
        self.index = index
        self._es = Elasticsearch(url or settings.elasticsearch_url, request_timeout=30)

    def ping(self) -> bool:
        try:
            return bool(self._es.ping())
        except Exception:  # noqa: BLE001
            return False

    def ensure_index(self, recreate: bool = False) -> None:
        if recreate and self._es.indices.exists(index=self.index):
            self._es.indices.delete(index=self.index)
        if not self._es.indices.exists(index=self.index):
            self._es.indices.create(
                index=self.index, mappings=ASSET_MAPPINGS, settings=ASSET_SETTINGS
            )

    def index_doc(self, doc_id: str, doc: Dict) -> None:
        self._es.index(index=self.index, id=doc_id, document=doc)

    def bulk_index(self, docs: List[Dict], id_field: str = "asset_id") -> int:
        actions = [
            {"_index": self.index, "_id": d[id_field], "_source": d} for d in docs
        ]
        success, _ = helpers.bulk(self._es, actions)
        self._es.indices.refresh(index=self.index)
        return success

    def search(self, query: Dict, size: int = 20) -> Dict:
        return self._es.search(index=self.index, query=query, size=size)

    def count(self) -> int:
        try:
            return int(self._es.count(index=self.index)["count"])
        except Exception:  # noqa: BLE001
            return 0

    def distinct_customer_ids(self) -> List[str]:
        """Which customers already have assets indexed (used to reconcile ingest state)."""
        try:
            if not self._es.indices.exists(index=self.index):
                return []
            r = self._es.search(
                index=self.index,
                size=0,
                aggs={"c": {"terms": {"field": "customer_id", "size": 1000}}},
            )
            return [b["key"] for b in r["aggregations"]["c"]["buckets"]]
        except Exception:  # noqa: BLE001
            return []

    def delete_index(self) -> None:
        if self._es.indices.exists(index=self.index):
            self._es.indices.delete(index=self.index)
