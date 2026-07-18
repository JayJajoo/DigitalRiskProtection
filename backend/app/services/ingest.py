"""Part-1 ingestion: embed a customer's assets, upsert to Chroma, index into Elasticsearch.

`ingest_customer_events` is a generator that yields progress dicts so the API can stream them
to the UI as Server-Sent Events (a small per-asset delay gives the live "real-time" feel).
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Dict, Iterator, List

from ..config import settings
from ..db.chroma_client import ChromaAssets
from ..db.es_client import ESAssets
from ..models import Customer
from .asset_docs import asset_chroma_metadata, asset_embedding_text, asset_es_doc
from .embeddings import embed_texts

PER_ASSET_DELAY = 0.15  # seconds; visual pacing for the live UI


class IngestionState:
    """Tracks which customers have been ingested this session (in-memory)."""

    def __init__(self) -> None:
        self._ingested: set[str] = set()
        self._lock = Lock()

    def mark(self, customer_id: str) -> None:
        with self._lock:
            self._ingested.add(customer_id)

    def is_ingested(self, customer_id: str) -> bool:
        return customer_id in self._ingested

    def all(self) -> List[str]:
        with self._lock:
            return sorted(self._ingested)

    def reconcile(self, customer_ids: List[str]) -> None:
        with self._lock:
            self._ingested.update(customer_ids)

    def unmark(self, customer_id: str) -> None:
        with self._lock:
            self._ingested.discard(customer_id)

    def clear(self) -> None:
        with self._lock:
            self._ingested.clear()


STATE = IngestionState()


def ingest_customer_events(customer: Customer) -> Iterator[Dict]:
    """Yield progress events while ingesting one customer's assets."""
    chroma = ChromaAssets()
    es = ESAssets()
    es.ensure_index()
    assets = customer.assets

    yield {
        "event": "start",
        "customer_id": customer.id,
        "customer_name": customer.name,
        "total_assets": len(assets),
    }

    try:
        texts = [asset_embedding_text(customer, a) for a in assets]
        metadatas = [asset_chroma_metadata(customer, a) for a in assets]
        es_docs = [asset_es_doc(customer, a) for a in assets]

        yield {"event": "embedding", "message": f"Embedding {len(assets)} asset(s) via OpenAI"}
        embeddings = embed_texts(texts) if assets else []
        yield {
            "event": "embedded",
            "count": len(embeddings),
            "model": settings.openai_embedding_model,
            "dim": len(embeddings[0]) if embeddings else 0,
        }

        if assets:
            chroma.upsert(
                ids=[a.id for a in assets],
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
        yield {"event": "vectors_stored", "count": len(assets)}

        if es_docs:
            es.bulk_index(es_docs)
        yield {"event": "indexed", "count": len(es_docs)}

        # Per-asset detail: the exact vector (preview), Chroma record, and ES document inserted.
        for i, a in enumerate(assets):
            emb = embeddings[i] if i < len(embeddings) else []
            yield {
                "event": "asset_done",
                "asset_id": a.id,
                "asset_type": a.type.value,
                "asset_value": a.value,
                "embedding": {
                    "model": settings.openai_embedding_model,
                    "dim": len(emb),
                    "preview": [round(float(x), 5) for x in emb[:8]],
                },
                "chroma": {"collection": "assets", "id": a.id, "document": texts[i], "metadata": metadatas[i]},
                "elasticsearch": {"index": es.index, "id": a.id, "document": es_docs[i]},
            }
            if PER_ASSET_DELAY:
                time.sleep(PER_ASSET_DELAY)

        STATE.mark(customer.id)
        yield {
            "event": "complete",
            "customer_id": customer.id,
            "assets_indexed": len(assets),
            "es_total": es.count(),
            "chroma_total": chroma.count(),
        }
    except Exception as exc:  # noqa: BLE001 - surface failures to the UI
        yield {"event": "error", "message": str(exc)}


def ingest_customer_sync(customer: Customer) -> int:
    """Non-streaming ingest of one customer (no per-asset delay). Returns asset count."""
    assets = customer.assets
    if not assets:
        STATE.mark(customer.id)
        return 0
    chroma = ChromaAssets()
    es = ESAssets()
    es.ensure_index()
    texts = [asset_embedding_text(customer, a) for a in assets]
    embeddings = embed_texts(texts)
    chroma.upsert(
        ids=[a.id for a in assets],
        embeddings=embeddings,
        documents=texts,
        metadatas=[asset_chroma_metadata(customer, a) for a in assets],
    )
    es.bulk_index([asset_es_doc(customer, a) for a in assets])
    STATE.mark(customer.id)
    return len(assets)


def ingest_all_sync() -> Dict:
    """Ingest every customer (used by POST /ingest/all and tests)."""
    from .catalog import all_customers

    total = sum(ingest_customer_sync(c) for c in all_customers())
    return {
        "customers_ingested": len(STATE.all()),
        "assets": total,
        "es_assets": ESAssets().count(),
        "chroma_vectors": ChromaAssets().count(),
    }


def reset_stores() -> Dict:
    """Wipe the ES index + Chroma collection + ingestion state (to replay the demo)."""
    es = ESAssets()
    es.delete_index()
    es.ensure_index()
    ChromaAssets().reset()
    STATE.clear()
    return {"reset": True, "es_assets": es.count(), "chroma_vectors": ChromaAssets().count()}
