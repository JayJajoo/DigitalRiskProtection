"""In-memory catalogue of seed data (profiles + content corpus), cached."""

from __future__ import annotations

from typing import List, Optional

from ..models import ContentItem, Customer
from .data_loader import load_corpus, load_profiles

_customers: Optional[List[Customer]] = None
_content: Optional[List[ContentItem]] = None


def all_customers() -> List[Customer]:
    global _customers
    if _customers is None:
        _customers = load_profiles()
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


def reload() -> None:
    """Drop caches so the next access re-reads the seed files."""
    global _customers, _content
    _customers = None
    _content = None
