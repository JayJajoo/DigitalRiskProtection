"""Load seed data (profiles + corpus) into validated Pydantic models.

Used by the seed validator now and by the Part-1/Part-2 pipelines later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..models import ContentItem, Customer

DATA_DIR = Path(__file__).resolve().parents[2] / "data"  # backend/data
PROFILES_DIR = DATA_DIR / "profiles"
CORPUS_FILE = DATA_DIR / "corpus" / "corpus.json"


def load_profiles() -> List[Customer]:
    """Self profile (if present) followed by every `entities*.json` batch."""
    customers: List[Customer] = []
    self_path = PROFILES_DIR / "self.private.json"
    if self_path.exists():
        customers.append(Customer.model_validate_json(self_path.read_text(encoding="utf-8")))
    for path in sorted(PROFILES_DIR.glob("entities*.json")):
        for raw in json.loads(path.read_text(encoding="utf-8")):
            customers.append(Customer.model_validate(raw))
    return customers


def load_corpus() -> List[ContentItem]:
    if not CORPUS_FILE.exists():
        return []
    raw = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
    return [ContentItem.model_validate(item) for item in raw]


def image_path(rel: str) -> Path:
    """Resolve a corpus image_path (e.g. 'images/knife.jpg') against the data dir."""
    return DATA_DIR / rel
