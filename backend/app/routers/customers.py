"""Customer catalogue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services.catalog import all_customers, get_customer
from ..services.ingest import STATE

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
def list_customers() -> list[dict]:
    return [
        {
            "id": c.id,
            "name": c.name,
            "type": c.type.value,
            "industry": c.industry,
            "protect_summary": c.protect_summary,
            "asset_count": len(c.assets),
            "ingested": STATE.is_ingested(c.id),
        }
        for c in all_customers()
    ]


@router.get("/{customer_id}")
def get_one(customer_id: str) -> dict:
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="customer not found")
    data = customer.model_dump()
    data["ingested"] = STATE.is_ingested(customer_id)
    return data
