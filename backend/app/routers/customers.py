"""Customer catalogue endpoints (+ suggest / create-and-ingest a new customer)."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException

from ..db.chroma_client import ChromaAssets
from ..db.es_client import ESAssets
from ..models import Customer
from ..services.catalog import add_customer, all_customers, delete_customer, get_customer
from ..services.ingest import STATE, ingest_customer_sync
from ..services.suggest import random_customer

router = APIRouter(prefix="/customers", tags=["customers"])


def _summary(c: Customer) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "type": c.type.value,
        "industry": c.industry,
        "protect_summary": c.protect_summary,
        "asset_count": len(c.assets),
        "ingested": STATE.is_ingested(c.id),
    }


@router.get("")
def list_customers() -> list[dict]:
    return [_summary(c) for c in all_customers()]


@router.get("/suggest")
def suggest() -> dict:
    """A random synthetic company to pre-fill the 'new customer' form."""
    data = random_customer().model_dump()
    data["ingested"] = False
    return data


@router.post("")
def create_customer(payload: Customer, ingest: bool = True) -> dict:
    """Create a new customer (fresh unique ids).

    By default it also embeds + indexes the assets into the stores. Pass ``ingest=false`` to
    only register the customer (un-ingested) so the UI can then replay ingestion via the SSE
    ``/ingest/{id}/stream`` endpoint and show the live per-asset log.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or "entity"
    cid = f"cust-new-{slug}-{uuid.uuid4().hex[:6]}"
    assets = [a.model_copy(update={"id": f"{cid}-a{i}"}) for i, a in enumerate(payload.assets)]
    customer = payload.model_copy(update={"id": cid, "assets": assets})

    add_customer(customer)
    if not ingest:
        return {"customer": customer.model_dump(), "assets_ingested": 0, "ingested": False}
    count = ingest_customer_sync(customer)
    return {"customer": customer.model_dump(), "assets_ingested": count, "ingested": True}


@router.get("/{customer_id}")
def get_one(customer_id: str) -> dict:
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")
    data = customer.model_dump()
    data["ingested"] = STATE.is_ingested(customer_id)
    return data


@router.delete("/{customer_id}")
def remove_customer(customer_id: str) -> dict:
    """Delete a customer and purge its assets from Chroma + Elasticsearch."""
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")
    ChromaAssets().delete([a.id for a in customer.assets])
    es_removed = ESAssets().delete_by_customer(customer_id)
    STATE.unmark(customer_id)
    delete_customer(customer_id)
    return {"deleted": customer_id, "es_docs_removed": es_removed}
