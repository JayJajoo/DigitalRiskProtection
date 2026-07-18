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
  a Claude **Opus** agent into a **per-asset verdict** (is_threat / severity / reason) with a
  company rollup — all replayable stage-by-stage in the UI.

The dataset is deliberately adversarial: 40 entities / 166 assets and a 242-item corpus that
includes homoglyph/leetspeak obfuscation, veiled threats, multilingual scams, and
false-positive/false-negative decoys.

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
1. Open **Part 1 · Ingestion**.
2. Click **Ingest** on the first customer (**Jay Jajoo**) and watch the live log embed each
   asset into Chroma and index it into Elasticsearch; the next customer unlocks.
3. Or click **Ingest all** to populate everything at once (166 assets). The pills up top show
   ES assets / Chroma vectors climbing. **Reset** clears the stores to replay.

### Part 2 · Pipeline
1. Open **Part 2 · Pipeline** and pick a content item. Good ones to try:
   - **`hard-t-2`** — a phishing lure using a **Cyrillic-homoglyph** `zеnpay.example`. Watch the
     enricher de-obfuscate it and the matcher hit the real **Zenpay** domain by exact match.
   - **`content-203`** — an **image** item (a knife) name-dropping Novabank's CEO. Vision detects
     the knife; the classifier flags a **physical threat** against the executive.
   - **`hard-d-2`** — a benign decoy ("I'll **KILL** this presentation"). Correctly cleared.
2. Hit **Play** to auto-advance, or **Step** through one stage at a time; **Pause** between
   stages; **Replay** to re-run. Click any stage in the timeline to inspect its **Input** and
   **Output** — enrichment JSON, vector candidates, exact/fuzzy matches, the de-duplicated
   asset list with provenance, and the final **per-asset verdicts + company rollup**.

> The stores may already be populated (166 assets) from development. A fresh backend reconciles
> its ingest state from Elasticsearch, so Part 2 matching works immediately. To demo Part 1 from
> scratch, click **Reset**.

---

## API surface (highlights)

| Method & path | Purpose |
|---|---|
| `GET /health`, `GET /stores/status` | Liveness + store/embedding status |
| `GET /customers`, `GET /customers/{id}` | Entity catalogue |
| `GET /ingest/{id}/stream` (SSE) | Ingest one customer with live progress |
| `POST /ingest/all`, `POST /ingest/reset` | Bulk ingest / wipe stores |
| `GET /content`, `GET /content/{id}`, `GET /content/{id}/image` | Corpus + image serving |
| `POST /content/{id}/enrich` / `/match` / `/analyze` | One-shot enrich / match / full chain |
| `POST /pipeline/start`, `POST /pipeline/{run_id}/step`, `GET /pipeline/{run_id}` | Stepped pipeline runs |

## Project structure

```
DRP/
  PROJECT.md  README.md  docker-compose.yml  .env.example
  backend/
    app/
      main.py  config.py
      models/            # Pydantic schemas (Customer, Asset, EnrichmentResult, ThreatResult, …)
      db/                # chroma_client.py, es_client.py
      services/          # embeddings, normalize, asset_docs, ingest, catalog,
                         # enrichment_agent, matcher, threat_agent, pipeline
      routers/           # health, stores, customers, ingest, content, pipeline
    data/                # profiles/ (self.private.json gitignored), corpus/, images/, seed/
    scripts/verify_stores.py
  frontend/
    src/{pages,components,lib}   # Part1Ingest, Part2Pipeline, ui/, api.ts
```

## Notes & caveats

- **Enrichment/classification need the `claude` CLI** on PATH (works in local dev off your Claude
  Code login; not in the slim backend Docker image).
- **Matcher = recall, classifier = precision.** The matcher casts a wide net (some fuzzy false
  positives); the Opus classifier makes the precise per-asset call and clears them.
- **All data is synthetic.** Filler entities use the reserved `.example` TLD; `credit_card` /
  `bank_account` values are standard **test** numbers only. The owner's real assets live in a
  **gitignored** `self.private.json` (+ gitignored corpus), so no PII is committed.
- **ZeroFox CTI** is deferred; the token is reserved in `.env` for a future connector.

## Status

Phases 0–8 complete: scaffold · data/seed · stores · Part-1 ingestion · enrichment · matcher ·
classifier · Part-2 UI · demo polish. See PROJECT.md §10 for the roadmap.
