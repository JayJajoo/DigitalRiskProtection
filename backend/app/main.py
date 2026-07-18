"""FastAPI application entrypoint for the DRP backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .routers import content, customers, health, ingest, metrics, pipeline, stores


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reconcile ingest state from Elasticsearch so a restart reflects already-indexed customers.
    try:
        from .db.es_client import ESAssets
        from .services.ingest import STATE

        STATE.reconcile(ESAssets().distinct_customer_ids())
    except Exception:  # noqa: BLE001 - never block startup on this
        pass
    yield


app = FastAPI(
    title="DRP — Digital Risk Protection API",
    version=__version__,
    description="Backend for the two-part DRP pipeline (asset ingestion + threat classification).",
    lifespan=lifespan,
)

# Frontend runs on Vite (5173) in dev and behind nginx in Docker; allow both plus
# same-origin proxying. Tighten before any non-demo deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(stores.router)
app.include_router(customers.router)
app.include_router(ingest.router)
app.include_router(content.router)
app.include_router(pipeline.router)
app.include_router(metrics.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "drp-backend",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
