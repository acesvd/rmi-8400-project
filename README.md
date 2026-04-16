# Claims Appeal OS Prototype (Local-First)

This project translates your prior document-intelligence stack into a case-centered insurance **Claims Appeal OS** prototype.

## What It Does (MVP)

- Create and manage appeal cases
- Upload denial/EOB/supporting documents
- Extract page-aware text and build retrievable chunks
- Produce structured Case JSON (payer, IDs, reasons, deadlines, missing docs, warnings)
- Generate route-based task checklists
- Generate grounded appeal letter drafts with citations
- Generate packet PDF bundles
- AI assistant chat for case Q&A (Ollama-first, fallback-safe)
- Log events (submitted/followup/decision/phone_call)

## Project Structure

- `backend/app/main.py` FastAPI app and endpoints
- `backend/app/services/` extraction, retrieval, case JSON, tasks, letter, packet
- `ui/app.py` Streamlit Home page
- `ui/pages/` multipage UI (`AI Chatbox`, `My Cases`)
- `ui/lib/` shared Streamlit helpers (API + reusable components)
- `storage/` uploaded files, artifacts, local SQLite file (fallback mode)
- `scripts/` local setup and run helpers

## Local Setup (No Docker)

### Prerequisites

- Python 3.12 (recommended and the version to use for local setup)
- `pip` and `venv`
- Tesseract OCR installed and available on your system `PATH` for image OCR (`.png`, `.jpg`, `.jpeg`, `.tiff`)
- Optional: Ollama if you want the full AI-powered extraction, letter drafting, and chat experience

Notes:

- PDF/TXT/DOCX flows work without Tesseract, but OCR for image uploads requires a local `tesseract` binary.
- On Windows, installing Tesseract usually means adding the install directory to `PATH` so `pytesseract` can find `tesseract.exe`.
- The setup scripts create a local virtual environment in `.venv` and install both backend and UI dependencies from `backend/requirements.txt` and `ui/requirements.txt`.
- Run scripts automatically load repo-root `.env` if present.

### macOS/Linux

From project root:

```bash
./scripts/setup_local.sh
cp .env.example .env
```

If your default `python3` is not Python 3.12, create/activate a Python 3.12 environment first and then run the setup script.

### Windows (PowerShell)

From project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local.ps1
Copy-Item .env.example .env
```

The PowerShell setup script prefers `python3.12` and will fall back to other Python 3 launchers if needed, but Python 3.12 is the expected local version for this project.

## Run Locally

### macOS/Linux

Terminal 1 (backend):

```bash
./scripts/run_backend.sh
```

Terminal 2 (UI):

```bash
./scripts/run_ui.sh
```

Single-command run (starts backend then UI):

```bash
./scripts/run_all_local.sh
```

### Windows (PowerShell)

Terminal 1 (backend):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_backend.ps1
```

Terminal 2 (UI):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_ui.ps1
```

Single-command run (starts backend then UI):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_all_local.ps1
```

Open:

- UI: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

In Streamlit, use the left navigation to switch between:
- `Home`
- `AI Chatbox`
- `My Cases`

## Ollama AI Mode (Primary)

The app is configured for **Ollama-first** behavior:

- Denial extraction: Ollama primary, regex/rule fallback
- Letter drafting: Ollama primary, template fallback
- Chat assistant: Ollama primary, rule-based fallback

Defaults:

- Base URL: `http://localhost:11434`
- Model: `llama3.1`

Quick start:

```bash
ollama pull llama3.1
ollama serve
```

Optional env vars:

- `APPEALS_OLLAMA_BASE_URL`
- `APPEALS_OLLAMA_API_KEY` (or `OLLAMA_API_KEY`)
- `APPEALS_OLLAMA_CHAT_MODEL`
- `APPEALS_OLLAMA_EXTRACT_MODEL`
- `APPEALS_OLLAMA_LETTER_MODEL`
- `APPEALS_OLLAMA_TIMEOUT`

### Ollama Cloud API Mode

For cloud deployments, point backend AI calls to Ollama Cloud API:

```bash
export APPEALS_OLLAMA_BASE_URL="https://ollama.com/api"
export APPEALS_OLLAMA_API_KEY="<your_ollama_api_key>"
export APPEALS_OLLAMA_CHAT_MODEL="gpt-oss:20b"
export APPEALS_OLLAMA_EXTRACT_MODEL="gpt-oss:20b"
export APPEALS_OLLAMA_LETTER_MODEL="gpt-oss:20b"
```

Notes:

- `APPEALS_OLLAMA_BASE_URL` accepts either `https://ollama.com` or `https://ollama.com/api`.
- If a model is configured with a `-cloud` suffix, it will be normalized automatically for Ollama Cloud API requests.

## Managed Database Mode (Cloud)

By default, the backend uses local SQLite (`APPEALS_DB_PATH`). For cloud deployments, set:

```bash
export APPEALS_DATABASE_URL="postgresql://USER:PASSWORD@/DB_NAME?host=/cloudsql/PROJECT:REGION:INSTANCE"
```

When `APPEALS_DATABASE_URL` is set, the backend uses PostgreSQL and ignores the local SQLite file path.

## Demo Flow (Class)

1. Create case
2. Upload denial letter (and optional EOB/records)
3. Run extraction
4. Generate tasks
5. Generate letter
6. Generate packet PDF
7. Log submitted/decision events

## Notes

- OCR for image uploads requires a local `tesseract` binary.
- Supported upload types: PDF, TXT, DOCX, PNG, JPG, JPEG, TIFF
- For a quick class demo, PDF/TXT/DOCX files are usually enough.
- Data defaults to local SQLite (`storage/appeals_os.db`), unless `APPEALS_DATABASE_URL` is configured.

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
- `GET /artifacts/{artifact_id}/download`
