# WindowsToMac.md — Replicate the DRP project on macOS (from scratch)

This is a **complete, do-every-step** runbook to bring up the **DRP (Digital Risk Protection)**
project on a Mac. It is written so that **a Claude agent (or a human)** can execute it
top‑to‑bottom with no prior knowledge of the project.

- Repo: `https://github.com/JayJajoo/DigitalRiskProtection`
- Original dev machine: Windows 11. This doc translates every Windows step to macOS
  (Apple Silicon **and** Intel).
- The repo already contains the **seed data** (profiles, corpus, images), so **no re-seeding is
  required**. You only create a `.env`, start Elasticsearch, ingest, and run.

> **If you are an automating agent:** run the sections in order. Each step has an explicit command
> and a **Verify** line — do not proceed until the Verify passes. A single copy‑paste block is in
> §12 "One‑shot bring‑up".

---

## 0. What this project is (so you know what "working" looks like)

Two‑part pipeline with a React UI + FastAPI backend:
- **Part 1 — Ingestion:** entity profiles → OpenAI embeddings → **Chroma** (vectors) + **Elasticsearch** (exact+fuzzy).
- **Part 2 — Pipeline:** content → **Claude Sonnet** enrichment → vector + string matching → **Claude Opus** per‑company threat classification, replayable stage‑by‑stage with live timers; timings saved to a SQLite `metrics.db`.

Services when running:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000` (docs at `/docs`)
- Elasticsearch: `http://localhost:9200`

---

## 1. Prerequisites (install these first)

### 1a. Homebrew (package manager)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Apple Silicon puts brew in /opt/homebrew; Intel in /usr/local. Follow the "Next steps" it prints
# to add brew to your PATH, then:
brew --version
```

### 1b. Git
```bash
brew install git      # or use the Xcode CLT git
git --version
```

### 1c. Python 3.11 (IMPORTANT: must be 3.11 — pinned deps like chromadb 0.5.5 need it)
```bash
brew install python@3.11
python3.11 --version   # -> Python 3.11.x
```
> Do **not** use 3.12/3.13 — some pinned deps won't build/resolve. Use the `python3.11` binary
> explicitly for the backend venv.

### 1d. Node 20+ (frontend + the Claude Code CLI)
```bash
brew install node@20
node --version   # -> v20.x or newer
npm --version
```

### 1e. Docker Desktop for Mac (for Elasticsearch)
- Download: https://www.docker.com/products/docker-desktop/ (pick **Apple Silicon** or **Intel**).
- Install, launch **Docker Desktop**, wait until it says "Docker Desktop is running".
- In Docker Desktop → **Settings → Resources**, give it **at least 4 GB RAM** (Elasticsearch needs ~1 GB + JVM overhead).
```bash
docker --version
docker compose version
docker info >/dev/null && echo "docker daemon OK"
```
**Verify:** `docker info` succeeds (daemon running). If it fails, open Docker Desktop and wait.

### 1f. Claude Code CLI (REQUIRED for Part‑2 enrichment/classification)
The Claude **Agent SDK** (used by the backend) runs on the Claude Code CLI. Install it and log in:
```bash
npm install -g @anthropic-ai/claude-code
claude --version
claude            # launches Claude Code; on first run choose "Log in" and complete the browser flow
```
- Logging in once stores credentials the SDK will reuse (no API key needed).
- **Alternative:** skip the login and instead put `ANTHROPIC_API_KEY=sk-ant-...` in `.env` (§3).
- Ensure `claude` is on PATH in the shell that will run the backend: `which claude`.

**Verify:** `which claude` prints a path, and either you completed `claude` login **or** you will set `ANTHROPIC_API_KEY`.

---

## 2. Clone the repository

```bash
cd ~/                     # or wherever you keep projects
git clone https://github.com/JayJajoo/DigitalRiskProtection.git
cd DigitalRiskProtection
ls                        # expect: PROJECT.md README.md docker-compose.yml backend/ frontend/ ...
```
**Verify:** `ls backend/data/corpus/corpus.json backend/data/profiles/*.json backend/data/images` all exist (the data is committed).

---

## 3. Create the `.env` (secrets are NOT in the repo)

The repo intentionally excludes `.env`. Create it at the **repo root** from the template:
```bash
cp .env.example .env
```
Now edit `.env` and set at minimum your **OpenAI** key (required for embeddings):
```bash
# open in your editor, e.g.:
nano .env
```
Set:
```dotenv
OPENAI_API_KEY=sk-...              # REQUIRED — your own OpenAI API key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
# ANTHROPIC_API_KEY=               # optional — leave blank if you did `claude` login in §1f
CLAUDE_ENRICHMENT_MODEL=claude-sonnet-5
CLAUDE_THREAT_MODEL=claude-opus-4-8
ELASTICSEARCH_URL=http://localhost:9200
CHROMA_PERSIST_DIR=./data/chroma
ZEROFOX_TOKEN=
```
Notes:
- `CHROMA_PERSIST_DIR=./data/chroma` is relative to the **backend/** working dir (that's where you run uvicorn).
- The backend reads `../.env` (repo root) when run from `backend/`, so keep `.env` at the repo root.

**Verify:** `grep OPENAI_API_KEY .env` shows your real key (not `sk-...`).

---

## 4. Start Elasticsearch (Docker)

From the repo root:
```bash
docker compose up -d elasticsearch
```
Wait ~20–40s for it to become healthy, then:
```bash
curl -s http://localhost:9200/_cluster/health | grep -o '"status":"[a-z]*"'
```
**Verify:** you see `"status":"green"` (or `"yellow"`). If the container keeps restarting, increase
Docker Desktop memory (§1e) and `docker compose up -d elasticsearch` again.

> Apple Silicon: the `docker.elastic.co/elasticsearch/elasticsearch:8.15.0` image is multi‑arch and
> runs natively on arm64. `vm.max_map_count` is handled inside Docker Desktop's VM — no host tuning needed.

---

## 5. Backend (FastAPI) — native run (recommended)

Run the backend **natively** (not in Docker) so it can reach your `claude` login for enrichment/classification.

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate               # macOS/Linux (NOT .venv/Scripts on Windows)
python -m pip install --upgrade pip
pip install -r requirements.txt         # installs fastapi 0.139.2, chromadb 0.5.5, openai, elasticsearch, claude-agent-sdk, etc.
```
Start the API:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Leave it running in this terminal. In a **new terminal**:
```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/stores/status
```
**Verify:** `/health` returns `{"status":"ok",...}` and `/stores/status` shows `elasticsearch.up: true`
and `embeddings.configured: true` (your OpenAI key is loaded).

---

## 6. Frontend (React/Vite)

In a **new terminal**, from the repo root:
```bash
cd frontend
npm install
npm run dev
```
**Verify:** it prints `Local: http://localhost:5173/`. Open that URL — the header shows a green dot
when it reaches the backend. (Use `localhost`, not `127.0.0.1`, for the frontend.)

---

## 7. Ingest the data (populate the stores)

The repo ships the profiles/corpus/images, but the **stores start empty** (Chroma + ES are gitignored).
Populate them one of two ways:

- **Fastest (bulk):**
  ```bash
  curl -s -X POST http://localhost:8000/ingest/all
  ```
- **Or in the UI:** open **Part 1 · Ingestion** → click **Ingest all** (or ingest customers one at a time to watch the live flow).

**Verify:**
```bash
curl -s http://localhost:8000/ingest/status
# expect es_assets and chroma_vectors > 0 (e.g. 166), ingested_customer_ids populated
```

---

## 8. Use it / end‑to‑end verification

1. **Part 1 · Ingestion:** customers show as ingested; "ES assets" / "Chroma vectors" pills > 0.
2. **Part 2 · Pipeline:** pick a content item (use the **type/label filters**, e.g. Label = `impersonation`
   or Type = `image`), press **Play**. Watch it flow: **Enrich → Vector → String → Dedup → Classify**,
   with a live timer per stage, ending in a per‑asset verdict + clickable company rollup.
3. **Metrics tab:** after a couple of runs, shows per‑stage average bars + per‑stage time‑series + a
   recent‑runs table, live from `metrics.db`.

Quick API smoke test of the full chain (enrich→match→classify) on one item:
```bash
curl -s -X POST http://localhost:8000/content/content-001/analyze | head -c 400
```
**Verify:** returns JSON with `enrichment`, `matches`, and `threat` keys (this exercises Claude Sonnet + Opus, so it needs §1f done).

---

## 9. Full‑Docker alternative (optional)

You can run everything in containers:
```bash
docker compose up --build         # elasticsearch + backend + frontend
# frontend -> http://localhost:5173, backend -> http://localhost:8000
```
**Caveat:** the backend container image has **no `claude` CLI**, so **Part‑2 enrichment/classification
won't work inside Docker**. Part 1 (ingestion) and browsing work. For the full demo, use the native
backend from §5 (which has your `claude` login). To stop: `docker compose down` (keeps the ES data volume).

---

## 10. Windows → macOS differences (quick reference)

| Thing | Windows (original) | macOS |
|---|---|---|
| venv activate | `.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| venv python | `.venv/Scripts/python.exe` | `.venv/bin/python` |
| Shell | PowerShell | bash/zsh |
| Package installs | winget / manual | Homebrew (`brew install …`) |
| Docker | Docker Desktop (Windows) | Docker Desktop (Mac, arm64/x86) |
| Stop a port | `Get-NetTCPConnection -LocalPort 8000 … Stop-Process` | `lsof -ti:8000 \| xargs kill -9` |
| Line endings | CRLF | LF (git normalizes; harmless warnings on clone) |
| Frontend host | use `localhost:5173` | same — Vite binds `localhost`/IPv6, not `127.0.0.1` |

---

## 11. Troubleshooting

- **`/health` works but `/content/*/analyze` returns 500 / "Claude Code returned an error result":**
  the `claude` CLI isn't logged in or isn't on PATH for the uvicorn shell. Do §1f (`claude` login) in
  the same shell/user, confirm `which claude`, restart uvicorn. (Note: the pipeline also has a
  deterministic fallback for content the model refuses, so some items still resolve without the LLM.)
- **Embeddings error / `openai_configured: false`:** `OPENAI_API_KEY` missing/invalid in `.env`. Fix §3, restart backend.
- **Elasticsearch container exits / `status` never green:** raise Docker Desktop memory to ≥4 GB (§1e); `docker compose up -d elasticsearch` again; check `docker logs drp-elasticsearch`.
- **`pip install` fails on chromadb/pydantic:** you're not on Python 3.11. Recreate the venv with `python3.11 -m venv .venv` (§5).
- **Port already in use (8000/5173/9200):** free it — `lsof -ti:8000 | xargs kill -9` (repeat per port).
- **Frontend can't reach API:** ensure backend is on `:8000` and you're opening `http://localhost:5173`. Vite proxies `/api` → `http://localhost:8000` (see `frontend/vite.config.ts`).
- **`claude` command not found:** `npm install -g @anthropic-ai/claude-code`; ensure npm global bin is on PATH (`npm bin -g`).
- **Chroma telemetry log spam:** harmless; already silenced in code.

---

## 12. One‑shot bring‑up (copy‑paste, after §1 prerequisites + §3 `.env`)

Assumes: prerequisites installed, `claude` logged in (or `ANTHROPIC_API_KEY` set), repo cloned, `.env` created with a real `OPENAI_API_KEY`.

```bash
# from repo root
docker compose up -d elasticsearch
until curl -s http://localhost:9200 >/dev/null; do echo "waiting for ES…"; sleep 3; done

# backend (new terminal)
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 &      # or run in its own terminal
until curl -s http://localhost:8000/health >/dev/null; do echo "waiting for API…"; sleep 2; done
curl -s -X POST http://localhost:8000/ingest/all >/dev/null && echo "ingested"

# frontend (new terminal, from repo root)
cd frontend && npm install && npm run dev
# open http://localhost:5173
```

**Definition of done:**
- `curl http://localhost:8000/ingest/status` shows `es_assets > 0` and `chroma_vectors > 0`.
- `http://localhost:5173` loads with a green API dot.
- In Part 2, playing an item produces a per‑asset threat verdict.

---

## 13. Regenerating data (only if you ever need to — not required)

The data is committed, so skip this normally. To rebuild the corpus/images from the seed scripts:
```bash
cd backend
source .venv/bin/activate
python data/seed/seed.py      # downloads open‑license images (needs internet) + regenerates corpus.json
```
Note: `self.private.json` (the owner profile) is committed in this repo, so the regenerated corpus
will include it. Images (`threat_kill_note.png`, `person_knife_named.png`) are regenerated by
`data/seed/make_threat_images.py` (invoked by `seed.py`), which needs `Pillow` (already in requirements).
