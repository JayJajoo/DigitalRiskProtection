"""OpenAI text-embedding service (single text vector space for the whole pipeline)."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from openai import OpenAI

from ..config import settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — cannot create embeddings.")
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: List[str], batch_size: int = 128) -> List[List[float]]:
    """Embed a list of texts, batched. Empty strings are replaced with a single space
    (the OpenAI API rejects empty input)."""
    if not texts:
        return []
    client = _client()
    cleaned = [t if (t and t.strip()) else " " for t in texts]
    out: List[List[float]] = []
    for i in range(0, len(cleaned), batch_size):
        chunk = cleaned[i : i + batch_size]
        resp = client.embeddings.create(model=settings.openai_embedding_model, input=chunk)
        out.extend(d.embedding for d in resp.data)
    return out


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]
