# DRP — Digital Risk Protection Pipeline

> A two-part Digital Risk Protection system. **Part 1** builds a data lake of real,
> high-profile entities and their public assets, embeds it into a vector DB and indexes it in
> Elasticsearch. **Part 2** ingests online content, enriches it with a Claude agent into
> structured JSON, matches it against the asset store (vector similarity + exact/fuzzy string
> match), de-duplicates per asset, and classifies each matched asset for threat & severity.

**Status:** Blueprint / planning document. Code is built in the phased roadmap at the end.
**Guiding principle:** *do not assume — every decision below was confirmed with the project owner.*

---

## 1. Overview & Goals

Digital Risk Protection (DRP) monitors the open web for content that threatens an
organization's or individual's protected assets (domains, social handles, brands,
executives) and raises prioritized, explained alerts.

This project demonstrates an end-to-end DRP pipeline with a web UI, split into two parts:

| Part                                                   | Goal                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Part 1 — Asset data lake & ingestion**        | Model 10 real famous people/companies, their**real public** assets, and the concerns/attack-types they'd want protected. Embed into **Chroma** and index into **Elasticsearch**. Ingest one customer at a time from a web UI.                                                                                                                              |
| **Part 2 — Enrichment & threat classification** | Take pre-collected online content, enrich it with**Claude Sonnet** into structured JSON + summary, embed it, match it against the asset store (**vector + exact/fuzzy string match**), de-duplicate per asset, then classify each matched asset with **Claude Opus** for `is_threat`/`severity`/`reason`. Replay it all in a web UI with pause/play. |

**Key design choice:** the data lake is anchored on **real entities with real public assets**
(not fully synthetic). This guarantees the collected online content genuinely overlaps the
asset store, so matches actually fire and the demo behaves like production. All data is
**pre-collected into static files**; the UI streams each item through the pipeline in **real
time** to simulate live operation.

---

## 2. Architecture

```
                          ┌──────────────────────────── PART 1: DATA LAKE & INGESTION ───────────────────────────┐
                          │                                                                                       │
  10 real entities  ─────►  profiles/*.json  ──►  [Ingest per customer]  ──►  OpenAI embeddings ──►  ┌─────────┐  │
  (real public assets)      (Customer/Asset/         (web UI, one at a time)                          │ Chroma  │  │
                             Concern)                       │                                         │ (vectors)│ │
                                                            └──────────────►  ES indexer  ──────────► ┌─────────┐  │
                                                                              (exact + fuzzy)         │Elastic- │  │
                                                                                                      │search   │  │
                          └───────────────────────────────────────────────────────────────────────  └────┬────┘  ┘
                                                                                                          │  ▲
                          ┌──────────────────────── PART 2: ENRICHMENT & CLASSIFICATION ─────────────────┼──┼─────┐
                          │                                                                              │  │     │
  pre-collected content ─►  ① Enrichment agent (Claude Sonnet)  ──►  structured JSON + summary          │  │     │
  (real + synthetic;         │                                              │                           │  │     │
   text + images)            │                                              ├─► ② Vector match ──────────┘  │     │
                             │                                              │      (embed text+JSON,        │     │
                             │                                              │       top-N / threshold)      │     │
                             │                                              └─► ③ String match ─────────────┘     │
                             │                                                     (exact keyword + fuzzy)        │
                             │                                                              │                     │
                             │                     ④ Merge + de-duplicate per asset (keep matched_by + score)     │
                             │                                              │                                     │
                             │                     ⑤ Threat agent (Claude Opus) — PER matched asset ──►           │
                             │                        is_threat / severity / reason  ──►  company_rollup          │
                             └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack & Rationale

| Area              | Choice                                                      | Why                                                                                                                             |
| ----------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Frontend          | **React + Vite + Tailwind + shadcn/ui** (light theme) | Largest ecosystem, clean light UI, easy SSE/WebSocket for live pipeline progress                                                |
| Backend           | **Python + FastAPI**                                  | Best fit for OpenAI, Elasticsearch, Chroma clients and the Claude Agent SDK                                                     |
| Agent framework   | **Claude Agent SDK (Python)**                         | Required by owner for both enrichment and classification                                                                        |
| Enrichment model  | **Claude Sonnet** (`claude-sonnet-5`, configurable) | Fast, strong at structured extraction + vision                                                                                  |
| Threat classifier | **Claude Opus** (`claude-opus-4-8`, configurable)   | Highest-quality reasoning for the final verdict                                                                                 |
| Embeddings        | **OpenAI** `text-embedding-3-small` (configurable)  | Owner supplies OpenAI creds; text-only vector space                                                                             |
| Vector DB         | **Chroma**                                            | Lightweight, easy local setup, good metadata filtering                                                                          |
| Keyword index     | **Elasticsearch** (Docker Compose, single-node)       | Exact`keyword` + fuzzy `text` matching                                                                                      |
| Infra             | **Docker Compose**                                    | One command to bring up ES + backend + frontend                                                                                 |
| Image handling    | **No raw-image embedding**                            | Images are described by the Sonnet vision enrichment; we embed the resulting**JSON + summary** (single text vector space) |

### `.env` contract

```dotenv
# LLM / embeddings
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
ANTHROPIC_API_KEY=sk-ant-...          # required by the Claude Agent SDK
CLAUDE_ENRICHMENT_MODEL=claude-sonnet-5
CLAUDE_THREAT_MODEL=claude-opus-4-8

# Data stores
ELASTICSEARCH_URL=http://localhost:9200
CHROMA_PERSIST_DIR=./backend/data/chroma

# Reserved for future CTI connector (unused in this build)
ZEROFOX_TOKEN=
```

> **Note:** `ANTHROPIC_API_KEY` was added beyond the owner's original list (OpenAI + ZeroFox),
> because the Claude Agent SDK needs Anthropic credentials.

---

## 4. Data Model

Pydantic models; persisted as JSON on disk and as metadata in Chroma + Elasticsearch.

- **`Customer`** — `id`, `name`, `type` (`person` | `company`), `description` ("what they are /
  what they want to protect"), `industry`.
- **`Asset`** — `id`, `customer_id`, `type` (`domain` | `social_handle` | `brand` | `executive`
  | `app` | `other`), `value`, `aliases[]`, `concerns[]`. Search-support fields derived at
  index time: `domain`, `handle`, `brand`, `executive`, `keywords[]`.
- **`Concern`** — attack type tied to an asset: `physical_attack` | `online_threat` |
  `impersonation` | `data_leak` | `financial_fraud` | `scam` | `mention`.
- **`ContentItem`** — `id`, `source`, `origin` (`real` | `synthetic`), `type` (`text` |
  `image` | `text+image`), `text`, `image_path`, `label` (ground-truth for demo).
- **`EnrichmentResult`**, **`ThreatVerdict`** — see §7.

> **No private PII is stored.** Assets are **real public** identifiers only (official domains,
> verified handles, brand/product names, publicly-known executives). "Credit-card / financial
> leak" is represented as a **concern type**, never as stored card data.

---

## 5. Part 1 — Data Lake & Ingestion

### Ingestion pipeline (per customer, triggered by the UI "Ingest" button)

For each `Asset` + its `Concern`s:

1. Build a text representation (`name + asset value + aliases + concern descriptions`).
2. OpenAI embedding → **upsert into Chroma** with metadata (`customer_id`, `asset_id`,
   `asset_type`, `concern`).
3. **Index the same doc into Elasticsearch** with both `keyword` sub-fields (exact match) and
   analyzed `text` fields (fuzzy match) on `domain`, `handle`, `brand`, `executive`, `keywords`.
4. Stream progress to the UI over SSE/WebSocket.
5. On completion, **reveal the next customer**; the operator clicks "Ingest" again.

### UI behaviour (Part 1 page)

- Left: list/cards of the 10 customers; only the current (and already-ingested) ones are active.
- Center: the selected customer's profile — who they are, assets, concerns.
- "Ingest" runs the pipeline with a live progress log (embedding → Chroma → ES) per asset.
- When done, the card is marked ingested and the next customer unlocks.

---

## 6. Part 2 — Enrichment, Matching & Classification

Staged, resumable orchestrator. The UI can **pause / play / replay** any stage and inspect its
output. Steps:

1. **Enrichment (Claude Sonnet).** Input = content text and/or image. Output = structured JSON
   (§7) + a natural-language summary. For images, the vision model fills `image_analysis` and
   `detected_text`.
2. **Vector match.** Embedding input = `content_text + summary + serialized_JSON` (for
   image-only items: `summary + JSON`). Embed via OpenAI → query Chroma → keep assets above the
   **top-N / similarity threshold**.
3. **String match (Elasticsearch, exact + fuzzy).** Extract the identity-bearing strings from
   the JSON and query the asset index (see the field map below).
4. **Merge + de-duplicate per `asset_id`.** Union the vector and string candidate sets, keeping
   provenance (`matched_by`: `vector`/`exact`/`fuzzy`) and the best score.
5. **Threat classification (Claude Opus) — one call per matched company.** De-duplicated assets
   are grouped by customer; each group's call runs concurrently → per-asset `is_threat` /
   `threat_type` / `reason`. **Severity is derived from the model's confidence** (>0.7 high, >0.5
   medium, ≤0.5 low). Results aggregate into a per-company rollup. If the LLM refuses a piece of
   content, deterministic regex/rule fallbacks keep the pipeline flagging genuinely-matched threats.

### Elasticsearch string-match field map

The **needles** are identity-bearing strings pulled from the enrichment JSON; the **haystack**
is each asset document. Risk-signal booleans are **not** asset keys — they feed the classifier.

| JSON field → query term                                                                           | Normalization                                               | Matched ES asset field(s)                                                        | Match type                                                    |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `entities.handles` + `targets_mentioned.assets`                                                | strip`@`, lowercase, extract root domain from emails/URLs | `asset.handle`, `asset.domain`, `asset.value`                              | exact (`term` on `.keyword`) **+ fuzzy** (`AUTO`) |
| `entities.persons` + `targets_mentioned.persons`                                               | lowercase, trim titles                                      | `asset.value`, `asset.aliases`, `asset.executive` (person/exec assets)     | exact + fuzzy                                                 |
| `entities.organizations` + `targets_mentioned.organizations` + `image_analysis.brands_logos` | lowercase                                                   | `asset.brand`, `asset.customer_name`, `asset.value` (brand/company assets) | exact + fuzzy                                                 |
| `entities.keywords`                                                                              | lowercase                                                   | `asset.keywords`, `asset.brand`                                              | fuzzy (lower boost)                                           |
| `detected_text` / `image_analysis.text_in_image` (OCR'd handles/domains)                       | tokenize + handle/domain normalization                      | `asset.handle`, `asset.domain`, `asset.brand`                              | exact + fuzzy                                                 |

**Query shape:** one `bool` query with `should` clauses — exact `term` on `.keyword`
sub-fields (high boost) **plus** fuzzy `multi_match` (`fuzziness: AUTO`) across analyzed
fields, with field boosts (`handles`/`domains` > `persons`/`brands` > `keywords`) and a
`min_score` cutoff. Each hit records which field/clause matched → becomes the `matched_by`
provenance carried into dedup and the per-asset verdict.

**Not used as asset-match keys** (they feed the classifier / severity, not matching):
`risk_signals`, `image_analysis` weapon/object flags, `languages`, `sentiment`,
`toxicity_score`. `summary` is optional low-boost full-text only.

### UI behaviour (Part 2 page)

- A content queue on the left; play processes them one at a time (real-time replay).
- A stage timeline (Enrich → Vector → String → Dedup → Classify) with **pause/play/replay**.
- Per-stage inspectors: raw content, enrichment JSON, vector matches (with scores), ES matches
  (with matched field), the de-duplicated candidate list, and the **per-asset verdict table**
  plus the **company rollup**.

---

## 7. Schemas

### 7.1 Enrichment output (Claude Sonnet) — **PROPOSED, please review/edit**

One list per key type, as requested.

```jsonc
{
  "content_id": "string",
  "content_type": "text | image | text+image",
  "summary": "concise natural-language summary of the content",
  "languages": ["en", "es"],              // languages present in the text
  "detected_text": "OCR/transcribed text found inside an image (empty if none)",
  "entities": {
    "persons":       ["named people mentioned"],
    "organizations": ["orgs mentioned"],
    "locations":     ["places mentioned"],
    "handles":       ["@handles / emails / domains found"],
    "keywords":      ["salient terms for ES exact/fuzzy match"]
  },
  "image_analysis": {                      // null when no image
    "person_present": true,
    "num_persons": 1,
    "weapons":  { "knife": true, "gun": false, "other": [] },
    "dangerous_objects": ["list"],
    "money_signs": true,                   // cash / "money-flipping" visual cues
    "scene_description": "string",
    "objects": ["general objects detected"],
    "brands_logos": ["list"],
    "text_in_image": "string"
  },
  "risk_signals": {                        // booleans, one per signal type
    "threat_language": false,
    "violence_indicator": false,
    "physical_threat": false,
    "money_flipping": false,
    "spam": false,
    "phishing": false,
    "scam": false,
    "impersonation": false,
    "doxxing_pii_exposure": false,
    "credential_or_data_leak": false,
    "hate_or_harassment": false
  },
  "targets_mentioned": {                   // who/what the content seems aimed at
    "persons": ["list"],
    "organizations": ["list"],
    "assets": ["emails / domains / handles referenced"]
  },
  "sentiment": "negative | neutral | positive",
  "toxicity_score": 0.0,                   // 0..1
  "confidence": 0.0                        // 0..1
}
```

### 7.2 Threat verdict (Claude Opus) — **one verdict per matched asset, rolled up per company**

```jsonc
{
  "content_id": "string",
  "asset_verdicts": [                       // one entry per de-duplicated matched asset
    {
      "asset_id": "string",
      "asset_type": "domain | social_handle | brand | executive | ...",
      "asset_value": "string",
      "customer_id": "string",
      "customer_name": "string",
      "matched_by": ["vector", "exact", "fuzzy"],   // provenance of the match
      "match_score": 0.0,                   // best similarity / relevance score
      "is_threat": true,
      "severity": "none | low | medium | high",
      "threat_type": "physical | reputational | financial | data-leak | scam | other",
      "reason": "why this content is/isn't a threat to THIS specific asset",
      "recommended_action": "string",
      "confidence": 0.0
    }
  ],
  "company_rollup": [                        // aggregation of asset_verdicts per customer
    {
      "customer_id": "string",
      "customer_name": "string",
      "max_severity": "none | low | medium | high",
      "threat_asset_count": 0,
      "summary": "string"
    }
  ]
}
```

---

## 8. Seed Data Plan

### 8.1 Entities — **PROPOSED candidate list of 10 (please edit/approve)**

Chosen for rich **public** assets and abundant **public** mentions (impersonation, phishing,
money-flipping and giveaway scams are common against all of them), across people, creators,
athletes, banks, crypto and consumer brands:

| #  | Entity                    | Type    | Example real public assets                | Typical concerns                                         |
| -- | ------------------------- | ------- | ----------------------------------------- | -------------------------------------------------------- |
| 1  | Elon Musk                 | person  | X`@elonmusk`, tesla.com, spacex.com     | impersonation, crypto "money-flipping" scams             |
| 2  | Taylor Swift              | person  | IG`@taylorswift`, taylorswift.com       | impersonation, harassment, deepfakes                     |
| 3  | Apple (Tim Cook)          | company | apple.com,`@Apple`, `@tim_cook`       | brand phishing, App Store scams                          |
| 4  | JPMorgan Chase            | company | jpmorganchase.com, chase.com,`@Chase`   | phishing, credential/data leak, financial fraud          |
| 5  | Cristiano Ronaldo         | person  | IG`@cristiano`, cristianoronaldo.com    | impersonation, giveaway scams                            |
| 6  | MrBeast (Jimmy Donaldson) | creator | YT`@MrBeast`, mrbeast.com               | crypto/giveaway scams, impersonation                     |
| 7  | Coinbase                  | company | coinbase.com,`@coinbase`                | phishing, crypto "flipping" scams, support impersonation |
| 8  | Google (Sundar Pichai)    | company | google.com,`@Google`, `@sundarpichai` | brand phishing, fake support                             |
| 9  | Nike                      | company | nike.com,`@Nike`                        | counterfeit stores, brand impersonation                  |
| 10 | Beyoncé                  | person  | IG`@beyonce`, beyonce.com               | impersonation, harassment                                |

### 8.2 Content corpus (~40–60 items)

Per entity: a few **real public mentions** (news snippets, public posts, publicly-reported
scam/impersonation examples referencing the brand) **plus synthetic** items (phishing emails
spoofing their domain, celebrity money-flipping/giveaway scams, impersonation handles) and
**benign/vague control** items. A subset are **image** items.

### 8.3 Images

Open-license / public-domain only:

- **Entity portraits** from Wikimedia Commons (public-domain / CC) → exercises
  `person_present` and entity recognition.
- **Object categories** (kitchen knife, cash stacks, buildings/places) from open-license stock
  → exercises `weapons`, `money_signs`, `objects`.

### 8.4 Storage & tooling

- Everything written to `backend/data/` as static JSON + image files → fully reproducible
  offline; the UI replays them in real time.
- `WebSearch` / `WebFetch` used by the seed scripts at build time to compile the dataset;
  results are frozen into the static files.

### 8.5 Safety boundary (enforced during data building)

- **No real private PII** (no real personal emails, phone numbers, card numbers).
- Only **already-public** mentions/news; no aggregation into a doxxing profile.
- **No fabricated credible violent physical threats against real named people.** Any
  "physical threat" sample stays clearly synthetic/generic or targets a fictional persona.
  Scam/phishing/impersonation/money-flipping samples (standard DRP patterns) are depicted
  generically.

---

## 9. Repository Layout

```
DRP/
  PROJECT.md  README.md  docker-compose.yml  .env.example
  backend/
    app/
      main.py            # FastAPI app + routers
      config.py          # env loading (pydantic-settings)
      models/            # Pydantic schemas (Customer, Asset, Concern, ContentItem, EnrichmentResult, ThreatVerdict)
      db/                # chroma_client.py, es_client.py
      services/          # embeddings, ingest, enrichment_agent, matcher, threat_agent, pipeline
      routers/           # customers, ingest, content, pipeline, ws (SSE/WebSocket)
    data/
      profiles/          # 10 real-entity profiles (JSON, public assets only)
      corpus/            # content items (real + synthetic; text + image refs)
      images/            # downloaded public-domain / open-license images
      chroma/            # Chroma persistence
      seed/              # research_entities.py, download_images.py, build_corpus.py
    requirements.txt / pyproject.toml
  frontend/
    src/
      pages/             # Part1Ingest, Part2Pipeline
      components/        # cards, stage timeline, JSON/inspector views, verdict tables
      api/               # backend client + SSE/WebSocket hooks
      lib/
    package.json  tailwind.config.js  vite.config.ts
```

---

## 10. Phased Build Roadmap

- **Phase 0 — Scaffold.** Repo, `docker-compose.yml` (Elasticsearch + backend + frontend),
  `.env.example`, FastAPI health check, React shell.
- **Phase 1 — Data model + seed.** Pydantic models; seed scripts to research 10 real entities +
  public assets, download public-domain/stock images, build the mixed real+synthetic corpus →
  static files.
- **Phase 2 — Stores.** Chroma + Elasticsearch clients; OpenAI embeddings service; ES mapping
  with `keyword` + analyzed `text` fields.
- **Phase 3 — Part 1 ingestion.** Ingestion service + sequential-ingest UI with live progress.
- **Phase 4 — Enrichment.** Claude Sonnet enrichment agent → structured JSON (+ image vision).
- **Phase 5 — Matcher.** Vector (top-N/threshold) + ES (exact + fuzzy) + de-duplicate per asset.
- **Phase 6 — Classifier.** Claude Opus per-asset threat verdict + company rollup.
- **Phase 7 — Part 2 UI.** Pipeline runner with pause/play/replay + per-stage inspectors.
- **Phase 8 — Demo & docs.** End-to-end pass, README run instructions.

### Post-build additions (beyond the original blueprint)

Design refinements made while building; the running system is described in **README.md**:
- **Rich entity context.** Every entity gets a generated description (HQ, revenue, headcount,
  fame; for people: spouse, net worth, cars). Each asset embeds as *entity context + the asset's
  unique info*, greatly improving semantic matching. Adds `vector_only` corpus items — no exact
  identifiers, so only the vector search catches them (verified: right entity, high severity).
- **Per-company classification** (one Opus call per matched customer, run concurrently) with
  **severity derived from confidence**, plus new `threat_type`s (assault / online-death / sextortion).
- **Deterministic fallbacks** for enrichment + classification when the LLM declines content.
- **Metrics DB** (SQLite) capturing per-stage + per-company timings, surfaced in a **Metrics tab**
  (charts + time series) and live timers in the pipeline.
- **Customer create / delete** (with store purge) and **re-ingest**; **live ingest detail**
  (embedding preview + Chroma record + ES document per asset); **content type/label filters**.

---

## 11. Open Questions, Assumptions & Out-of-Scope

- **Enrichment schema (§7.1) and the 10-entity list (§8.1) are proposals** awaiting owner
  review/edits before Phase 1.
- **`ANTHROPIC_API_KEY` added** to the `.env` contract (Agent SDK requirement) — beyond the
  owner's original OpenAI + ZeroFox list.
- **ZeroFox CTI is deferred.** `ZEROFOX_TOKEN` is reserved in `.env` for a future pluggable
  connector; not used in this build. (Rationale: records can be pulled but not searched, so the
  underlying public data sources are the useful part — to be revisited later.)
- **Similarity threshold / top-N** and **ES field boosts / `min_score`** are tunable
  parameters; sensible defaults chosen in Phase 5, exposed in config.
- **Safety boundary (§8.5)** is enforced while building the dataset.

---

## 12. Verification

For each build phase, the end-to-end check is:

1. `docker compose up` (Elasticsearch + backend + frontend).
2. Seed the data (`backend/data/seed/*`).
3. In the Part 1 UI, ingest customers one by one; confirm Chroma + Elasticsearch populate.
4. In the Part 2 UI, play a content item; confirm the pipeline yields an **enrichment JSON**,
   **candidate matches** (vector + exact/fuzzy ES, de-duplicated per asset), and a
   **per-asset threat verdict** + company rollup.
5. Spot-check a known phishing/impersonation item against its expected entity to confirm the
   match and severity are correct.
