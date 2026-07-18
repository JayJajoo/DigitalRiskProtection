"""In-memory catalogue of seed data (profiles + content corpus), cached."""

from __future__ import annotations

import json
from typing import List, Optional

from ..models import ContentItem, Customer
from .data_loader import PROFILES_DIR, load_corpus, load_profiles

_customers: Optional[List[Customer]] = None
_content: Optional[List[ContentItem]] = None

DELETED_FILE = PROFILES_DIR / "deleted_ids.json"
USER_ADDED_FILE = PROFILES_DIR / "entities.user-added.json"


def _load_deleted() -> set[str]:
    if DELETED_FILE.exists():
        try:
            return set(json.loads(DELETED_FILE.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            return set()
    return set()


def all_customers() -> List[Customer]:
    global _customers
    if _customers is None:
        deleted = _load_deleted()
        _customers = [c for c in load_profiles() if c.id not in deleted]
    return _customers


def get_customer(customer_id: str) -> Optional[Customer]:
    return next((c for c in all_customers() if c.id == customer_id), None)


def all_content() -> List[ContentItem]:
    global _content
    if _content is None:
        _content = load_corpus()
    return _content


def get_content(content_id: str) -> Optional[ContentItem]:
    return next((x for x in all_content() if x.id == content_id), None)


def add_customer(customer: Customer) -> None:
    """Append a user-created customer: persist to entities.user-added.json + update the cache."""
    existing = []
    if USER_ADDED_FILE.exists():
        try:
            existing = json.loads(USER_ADDED_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            existing = []
    existing.append(customer.model_dump())
    USER_ADDED_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    all_customers().append(customer)


def delete_customer(customer_id: str) -> None:
    """Persistently hide a customer: tombstone it + drop from the user-added file + cache.
    (Tombstone avoids rewriting the committed seed files for fake/batch entities.)"""
    deleted = _load_deleted()
    deleted.add(customer_id)
    DELETED_FILE.write_text(json.dumps(sorted(deleted), indent=2), encoding="utf-8")

    if USER_ADDED_FILE.exists():
        try:
            arr = json.loads(USER_ADDED_FILE.read_text(encoding="utf-8"))
            arr = [c for c in arr if c.get("id") != customer_id]
            USER_ADDED_FILE.write_text(json.dumps(arr, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    global _customers
    if _customers is not None:
        _customers = [c for c in _customers if c.id != customer_id]


def reload() -> None:
    """Drop caches so the next access re-reads the seed files."""
    global _customers, _content
    _customers = None
    _content = None
