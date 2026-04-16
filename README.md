# Claims Appeal OS Prototype (Deployment Branch)

This `deployment` branch is the cloud-ready version of the project for grading/demo access.

It keeps the same product workflow as `main`, but the runtime architecture is different so the app can be accessed without your laptop running 24/7.

## Branch Intent

- `main`: local-first development and classroom demos from your machine.
- `deployment`: hosted Streamlit + hosted FastAPI + managed storage/DB + hosted LLM.

If behavior differs between environments, follow this README for the `deployment` branch.

## Main vs Deployment (At a Glance)

| Area | `main` (local-first) | `deployment` (cloud-first) |
|---|---|---|
| UI host | Local Streamlit | Streamlit Community Cloud |
| API host | Local FastAPI | Cloud Run FastAPI |
| LLM runtime | Local Ollama (`llama3.1`) by default | Ollama Cloud API (e.g. `gpt-oss:20b`) |
| Database | Local SQLite (`storage/appeals_os.db`) | Postgres via `APPEALS_DATABASE_URL` (e.g. Neon) |
| File storage | Local disk under `storage/` | Cloud Storage bucket mount for uploads/artifacts |
| Availability | Only while your machine is on | Cloud-hosted (free-tier cold starts possible) |

## Deployed Architecture

- Streamlit app (`ui/app.py`) runs on Streamlit Community Cloud.
- Streamlit calls FastAPI backend via `APPEALS_API_URL`.
- FastAPI runs on Cloud Run.
- FastAPI persists relational data to Postgres (`APPEALS_DATABASE_URL`).
- Uploaded files and generated artifacts are stored in mounted Cloud Storage paths.
- AI calls route through Ollama-compatible API settings (`APPEALS_OLLAMA_*`).

## What It Does (MVP)

- Create and manage appeal cases
- Upload denial/EOB/supporting documents
- Extract page-aware text and build retrievable chunks
- Produce structured Case JSON (payer, IDs, reasons, deadlines, missing docs, warnings)
- Generate route-based task checklists
- Generate grounded appeal letter drafts with citations
- Generate packet PDF bundles
- AI assistant chat for case Q&A
- Log events (submitted/followup/decision/phone_call)

## Deployment Environment Variables

Set these on Cloud Run for backend:

- `APPEALS_DATABASE_URL` (required for cloud persistence)
- `APPEALS_OLLAMA_BASE_URL`
- `APPEALS_OLLAMA_API_KEY`
- `APPEALS_OLLAMA_CHAT_MODEL`
- `APPEALS_OLLAMA_EXTRACT_MODEL`
- `APPEALS_OLLAMA_LETTER_MODEL`
- `APPEALS_OLLAMA_TIMEOUT`

Set these in Streamlit Community Cloud secrets:

- `APPEALS_API_URL`
- `APPEALS_API_TIMEOUT`
- `CLAIMRIGHT_UI_USERNAME`
- `CLAIMRIGHT_UI_PASSWORD`
- `DEMO_MODE` (`true` or `false`)

Example backend model config (Ollama Cloud API):

```bash
APPEALS_OLLAMA_BASE_URL=https://ollama.com
APPEALS_OLLAMA_CHAT_MODEL=gpt-oss:20b
APPEALS_OLLAMA_EXTRACT_MODEL=gpt-oss:20b
APPEALS_OLLAMA_LETTER_MODEL=gpt-oss:20b
```

## Demo Mode Toggle + Disclaimer

This branch includes a UI demo lock for classroom presentations.

- `DEMO_MODE=true`:
  - Disables `New Case` actions
  - Disables document upload controls
  - Disables `Compute/Recompute A-Score`
  - Shows a modal disclaimer after login in `ui/app.py`
- `DEMO_MODE=false`:
  - Restores normal UI behavior

Current implementation defaults to demo mode if `DEMO_MODE` is not set:

```bash
DEMO_MODE=true
```

For a full interactive run, set this in Streamlit secrets:

```bash
DEMO_MODE=false
```

Disclaimer text shown in demo mode:

- Prototype is configured for classroom live demo on free-tier resources.
- New Case, Upload, and A-Score recomputation are temporarily disabled.
- Two demo cases are preloaded for viewing.

## Cloud Deployment Flow (This Branch)

### 1) Build and deploy backend to Cloud Run

From repo root:

```bash
PROJECT_ID="<your-project>"
REGION="us-east1"
REPO="appeals"
SERVICE="appeals-api"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:latest"

# Apple Silicon safe build target
docker buildx build --platform linux/amd64 -f backend/Dockerfile -t "$IMAGE" --push .

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8000
```

### 2) Attach DB and AI env vars

```bash
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars APPEALS_DATABASE_URL="<postgres-url>",APPEALS_OLLAMA_BASE_URL="https://ollama.com",APPEALS_OLLAMA_API_KEY="<key>",APPEALS_OLLAMA_CHAT_MODEL="gpt-oss:20b",APPEALS_OLLAMA_EXTRACT_MODEL="gpt-oss:20b",APPEALS_OLLAMA_LETTER_MODEL="gpt-oss:20b",APPEALS_OLLAMA_TIMEOUT="180"
```

### 3) Set Streamlit app to this branch

In Streamlit Community Cloud settings:

- Branch: `deployment`
- Main file path: `ui/app.py`
- Secrets include `APPEALS_API_URL=<cloud-run-url>`

## Local Run (Still Supported)

You can still run this branch locally for debugging.

### macOS/Linux

```bash
./scripts/setup_local.sh
cp .env.example .env
./scripts/run_all_local.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local.ps1
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File .\scripts\run_all_local.ps1
```

## Notes on A-Score Behavior

A-Score now supports persistent saved results in backend storage:

- It shows the last saved score when available.
- It recomputes only when explicitly requested.
- Cache status is surfaced via API metadata (`_cache`).

## Project Structure

- `backend/app/main.py` FastAPI app and endpoints
- `backend/app/services/` extraction, retrieval, case JSON, tasks, letter, packet, A-score logic
- `backend/app/database.py` DB setup and connection mode (SQLite fallback or Postgres URL)
- `backend/Dockerfile` backend container image build
- `ui/app.py` Streamlit router/shell page
- `ui/pages/` multipage UI (`AI Chatbox`, `My Cases`, `A-Score`, etc.)
- `ui/lib/` shared Streamlit helpers
- `scripts/` local setup and run helpers

## Operational Caveats (Free Tier)

- Streamlit Community Cloud can hibernate after inactivity.
- First request after idle may take extra startup time.
- Cloud free tiers can enforce request/quota limits.

For grading submissions, disclose possible wake-up/cold-start delay.

## Core API Endpoints

- `POST /cases`
- `GET /cases`
- `GET /cases/{case_id}`
- `POST /cases/{case_id}/documents`
- `POST /cases/{case_id}/process`
- `POST /cases/{case_id}/extract`
- `POST /cases/{case_id}/tasks/generate`
- `POST /cases/{case_id}/letter`
- `POST /cases/{case_id}/packet`
- `POST /cases/{case_id}/chat`
- `POST /cases/{case_id}/events`
- `GET /cases/{case_id}/appealability`
- `GET /artifacts/{artifact_id}/download`
