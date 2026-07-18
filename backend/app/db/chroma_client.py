"""Chroma vector-store wrapper for the asset collection.

We supply our own (OpenAI) embeddings, so the collection uses no embedding function and we
pass vectors explicitly. Cosine space; similarity is reported as 1 - distance.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings

# chromadb 0.5.x has a telemetry-capture signature bug that logs harmless errors even with
# telemetry disabled; silence that specific logger.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)


class ChromaAssets:
    def __init__(self, collection_name: str = "assets", persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict],
    ) -> None:
        self._col.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def query(
        self,
        embedding: List[float],
        n_results: int = 10,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        res = self._col.query(
            query_embeddings=[embedding], n_results=n_results, where=where
        )
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        out: List[Dict] = []
        for i, _id in enumerate(ids):
            dist = dists[i] if i < len(dists) else None
            out.append(
                {
                    "id": _id,
                    "distance": dist,
                    "score": (1.0 - dist) if dist is not None else None,
                    "metadata": metas[i] if i < len(metas) else {},
                    "document": docs[i] if i < len(docs) else "",
                }
            )
        return out

    def count(self) -> int:
        return self._col.count()

    def reset(self) -> None:
        """Drop and recreate the collection (used before a full re-ingest)."""
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:  # noqa: BLE001 - fine if it didn't exist
            pass
        self._col = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
