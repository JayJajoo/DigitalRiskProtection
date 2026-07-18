"""Phase-2 smoke test: exercise OpenAI embeddings + Chroma + Elasticsearch end-to-end
on a temporary index/collection using real profile data, then clean up.

Run from the backend directory (Elasticsearch must be up):
    cd backend && python scripts/verify_stores.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db.chroma_client import ChromaAssets  # noqa: E402
from app.db.es_client import ESAssets  # noqa: E402
from app.services.asset_docs import (  # noqa: E402
    asset_chroma_metadata,
    asset_embedding_text,
    asset_es_doc,
)
from app.services.data_loader import load_profiles  # noqa: E402
from app.services.embeddings import embed_texts  # noqa: E402

SMOKE = "assets_smoke"


def main() -> None:
    customers = load_profiles()
    sample = [(c, a) for c in customers for a in c.assets][:8]
    print(f"Sample: {len(sample)} assets (first customer: {customers[0].name})\n")

    # ── Elasticsearch: index + exact + fuzzy ──
    es = ESAssets(index=SMOKE)
    print("Elasticsearch ping:", es.ping())
    es.ensure_index(recreate=True)
    es.bulk_index([asset_es_doc(c, a) for c, a in sample])
    print("  indexed docs:", es.count())

    val = sample[0][1].value
    exact = es.search({"term": {"value.keyword": val.lower()}})
    print(f"  exact  '{val}': {exact['hits']['total']['value']} hit(s)")

    typo = (val[:-1] + "z") if len(val) > 3 else val
    fuzzy = es.search(
        {
            "multi_match": {
                "query": typo,
                "fields": ["value", "aliases", "domain", "handle", "brand"],
                "fuzziness": "AUTO",
            }
        }
    )
    print(f"  fuzzy  '{typo}': {fuzzy['hits']['total']['value']} hit(s)")
    es.delete_index()

    # ── OpenAI embeddings + Chroma: upsert + semantic query ──
    texts = [asset_embedding_text(c, a) for c, a in sample]
    embs = embed_texts(texts)
    print(f"\nEmbedded {len(embs)} texts (dim={len(embs[0])})")

    chroma = ChromaAssets(collection_name=SMOKE)
    chroma.reset()
    chroma.upsert(
        ids=[a.id for _, a in sample],
        embeddings=embs,
        documents=texts,
        metadatas=[asset_chroma_metadata(c, a) for c, a in sample],
    )
    print("  chroma vectors:", chroma.count())

    q = f"phishing email pretending to be from {sample[0][0].name}"
    hits = chroma.query(embed_texts([q])[0], n_results=3)
    print(f"  semantic query: '{q}'")
    for h in hits:
        m = h["metadata"]
        print(f"    {h['score']:.3f}  {m['asset_type']}={m['asset_value']}  ({m['customer_name']})")
    chroma._client.delete_collection(SMOKE)

    print("\nPhase 2 stores OK — embeddings + Chroma + Elasticsearch all working.")


if __name__ == "__main__":
    main()
