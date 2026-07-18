# DRP — Digital Risk Protection Pipeline

An end-to-end **Digital Risk Protection** demo with a web UI. See **[PROJECT.md](./PROJECT.md)**
for the full architecture, schemas, and design decisions.

- **Part 1 — Asset data lake & ingestion.** A catalogue of entities (the project owner as the
  primary protected entity + 39 fully-fake filler entities) and their assets. Each asset is
  embedded into **Chroma** and indexed into **Elasticsearch**, one customer at a time, from a
  web UI with live progress.
- **Part 2 — Enrichment & threat classification.** Collected content is enriched by a Claude
  **Sonnet** agent into structured JSON (+ image vision), matched back to the assets via
  **vector similarity + exact/fuzzy string match**, de-duplicated per asset, then classified by
  a Claude **Opus** agent — **one call per matched company** — into per-asset verdicts
  (is_threat / threat_type / reason). **Severity is derived from confidence** (>0.7 high, >0.5
  medium, ≤0.5 low) and rolled up per company. Everything replays stage-by-stage with live timers,
  and stage timings are saved to a SQLite `metrics.db` surfaced in a **Metrics** tab.

The dataset is deliberately adversarial: 40 entities / 166 assets and a ~250-item corpus with
homoglyph/leetspeak obfuscation, veiled threats, multilingual scams, false-positive/negative
decoys, **image-only** threats (name + weapon, OCR-extracted), and **`vector_only`** items that no
string match catches (only the semantic vector search does). Each entity carries a **rich context
description** (HQ, revenue, headcount, what they're famous for, etc.) that is baked into its asset
embeddings for stronger semantic matching. If the LLM refuses a piece of content, deterministic
regex/rule fallbacks keep the pipeline flagging real threats.

---

## Tech stack

React + Vite + Tailwind + shadcn/ui · FastAPI (Python) + **Claude Agent SDK** (Sonnet enrichment,
Opus classification) · OpenAI embeddings · **Chroma** (vectors) · **Elasticsearch** (exact + fuzzy) ·
Docker Compose.

## Prerequisites

- **Python 3.11+**, **Node 20+**, **Docker** (for Elasticsearch).
- **OpenAI API key** (embeddings) — required.
- **Claude auth** — the Agent SDK runs on the **Claude Code CLI**, so it uses your existing
  `claude` login (run `claude login` once). `ANTHROPIC_API_KEY` is optional (only needed for
  API-based billing or inside Docker). The `claude` CLI must be on your PATH at runtime.

## Setup

```bash
cp .env.example .env      # then set OPENAI_API_KEY (ANTHROPIC_API_KEY optional)
```

`.env` keys: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `ANTHROPIC_API_KEY` (optional),
`CLAUDE_ENRICHMENT_MODEL`, `CLAUDE_THREAT_MODEL`, `ELASTICSEARCH_URL`, `CHROMA_PERSIST_DIR`,
`ZEROFOX_TOKEN` (reserved/unused).

## Run (recommended: local dev)

Elasticsearch runs in Docker; the backend + frontend run natively (hot reload, and the backend
can reach your `claude` login for enrichment/classification).

```bash
# 1) Elasticsearch
docker compose up -d elasticsearch

# 2) Backend  (http://localhost:8000 — docs at /docs)
cd backend
python -m venv .venv && . .venv/Scripts/activate     # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python data/seed/seed.py         # build corpus + images (first run only)
uvicorn app.main:app --reload

# 3) Frontend  (http://localhost:5173)
cd frontend
npm install
npm run dev
```

> **Full-stack Docker** (`docker compose up --build`) also works for Part 1 + browsing, but the
> slim backend image has no `claude` CLI, so Part-2 enrichment/classification won't run there.
> Use local dev for the full demo.

---

## Guided demo

### Part 1 · Ingestion
1. Open **Part 1 · Ingestion**. Selecting a customer shows its **rich description** (context) +
   what it protects + its assets/concerns.
2. Click **Ingest** (or **Re-ingest** on an already-done one) and watch the live log embed each
   asset into Chroma and index it into Elasticsearch. **Expand any `✓ asset` line** to see exactly
   what was written — the OpenAI embedding (dim 1536 + preview), the Chroma record, and the
   Elasticsearch document.
3. **Ingest all** populates everything at once (166 assets); the top pills show ES assets / Chroma
   vectors climbing. **Reset** wipes the stores to replay.
4. **+ New customer** opens a form pre-filled with a random fake company (with a rich description);
   edit or **Randomize**, then **Add & ingest** to embed + index it immediately. The **🗑** on each
   row deletes a customer and purges its assets from both stores.

### Part 2 · Pipeline
1. Open **Part 2 · Pipeline**. Filter the queue by **content type** (text / image / text+image) or
   **label** (phishing, scam, doxxing, `vector_only`, …). Good items to try:
   - **`hard-t-2`** — a phishing lure using a **Cyrillic-homoglyph** `zеnpay.example`; the enricher
     de-obfuscates it and the matcher hits the real **Zenpay** by exact match.
   - **`content-210` / `content-211`** — **image-only** threats; vision OCRs a name + detects a
     weapon and flags a physical threat.
   - a **`vector_only`** item (label filter) — no exact identifiers, so string match finds nothing
     while the **vector search** surfaces the right entity.
   - **`hard-d-2`** — a benign decoy ("I'll **KILL** this presentation"). Correctly cleared.
2. **Play** auto-advances (with a live per-stage timer), **Step** does one stage, **Pause** between
   stages, **Replay** re-runs. Click any stage to inspect its **Input** and **Output** — enrichment
   JSON, vector candidates, exact/fuzzy matches, the de-duplicated list with provenance, and the
   **per-asset verdicts + company rollup** (click a company to see its full description).
3. The **Metrics** tab charts per-stage average timings + a per-stage time series, read live from
   `metrics.db`.

> The stores may already be populated (166 assets) from development. A fresh backend reconciles
> its ingest state from Elasticsearch, so Part 2 matching works immediately. To demo Part 1 from
> scratch, click **Reset**.

---

## API surface (highlights)

| Method & path | Purpose |
|---|---|
| `GET /health`, `GET /stores/status` | Liveness + store/embedding status |
| `GET /customers`, `GET /customers/{id}` | Entity catalogue |
| `GET /customers/suggest`, `POST /customers`, `DELETE /customers/{id}` | Suggest / create+ingest / delete (purges both stores) |
| `GET /ingest/{id}/stream` (SSE) | Ingest one customer (live progress incl. embedding + records) |
| `POST /ingest/all`, `POST /ingest/reset` | Bulk ingest / wipe stores |
| `GET /content`, `GET /content/{id}`, `GET /content/{id}/image` | Corpus + image serving |
| `POST /content/{id}/enrich` / `/match` / `/analyze` | One-shot enrich / match / full chain |
| `POST /pipeline/start`, `POST /pipeline/{run_id}/step`, `GET /pipeline/{run_id}` | Stepped pipeline runs |
| `GET /metrics/summary` | Aggregate pipeline stage timings (from `metrics.db`) |

## Project structure

```
DRP/
  PROJECT.md  README.md  docker-compose.yml  .env.example
  backend/
    app/
      main.py  config.py
      models/            # Pydantic schemas (Customer, Asset, EnrichmentResult, ThreatResult, …)
      db/                # chroma_client.py, es_client.py, metrics_db.py
      services/          # embeddings, normalize, asset_docs, entity_profile, ingest, catalog,
                         # suggest, enrichment_agent, matcher, threat_agent, agent_common, pipeline
      routers/           # health, stores, customers, ingest, content, pipeline, metrics
    data/                # profiles/, corpus/, images/, seed/ (seed.py, enrich_descriptions.py,
                         # download_images.py, make_threat_images.py, build_corpus.py)
    scripts/verify_stores.py
  frontend/
    src/{pages,components,lib}   # Part1Ingest, Part2Pipeline, Metrics, ui/, api.ts
```

## Notes & caveats

- **Enrichment/classification need the `claude` CLI** on PATH (works in local dev off your Claude
  Code login; not in the slim backend Docker image).
- **Matcher = recall, classifier = precision.** The matcher casts a wide net (some fuzzy false
  positives); the Opus classifier makes the precise per-asset call and clears them.
- **Data.** Filler entities are fully synthetic (reserved `.example` TLD; `credit_card` /
  `bank_account` are standard **test** numbers only). The owner's own profile (`self.private.json`)
  and the generated corpus are **committed at the owner's explicit request**, so they include the
  owner's real contact details; only `.env` (the API key) is excluded.
- **Rich entity context.** Each entity has a generated description (HQ, revenue, headcount, fame,
  and — for people — spouse/net-worth/cars) baked into its asset embeddings for stronger semantic
  matching. Regenerate with `data/seed/enrich_descriptions.py`.
- **ZeroFox CTI** is deferred; the token is reserved in `.env` for a future connector.

## Status

Phases 0–8 complete (scaffold · data/seed · stores · ingestion · enrichment · matcher · classifier
· Part-2 UI · polish), plus post-build additions: **rich entity descriptions** in embeddings,
**per-company classification**, **confidence-derived severity**, deterministic **LLM fallbacks**, a
**metrics DB + Metrics tab**, **customer create/delete + re-ingest**, **content type/label
filters**, **live ingest detail**, and **`vector_only`** examples. See PROJECT.md §10 for the roadmap.
