"""Seed orchestrator: build images + corpus, then validate everything against the models.

Run from the backend directory (so `app` is importable):
    cd backend && python data/seed/seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app` importable when run as a script.
BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import build_corpus  # noqa: E402  (same directory)
import download_images  # noqa: E402
import make_threat_images  # noqa: E402


def main() -> None:
    print("== 1/3 images ==")
    download_images.main()
    make_threat_images.main()

    print("\n== 2/3 corpus ==")
    build_corpus.main()

    print("\n== 3/3 validate against Pydantic models ==")
    from app.services.data_loader import load_corpus, load_profiles  # noqa: E402

    customers = load_profiles()
    corpus = load_corpus()
    total_assets = sum(len(c.assets) for c in customers)
    persons = sum(1 for c in customers if c.type.value == "person")
    companies = sum(1 for c in customers if c.type.value == "company")

    print(f"Profiles: {len(customers)} customers "
          f"({persons} person / {companies} company), {total_assets} assets total")
    for c in customers:
        print(f"  - {c.name:22s} [{c.type.value:7s}] {len(c.assets)} assets")
    print(f"Corpus:   {len(corpus)} content items validated OK")

    if not any(c.id == "cust-self" for c in customers):
        print("NOTE: self.private.json not found — seeded with fake entities only.")
    print("\nSeed complete.")


if __name__ == "__main__":
    main()
