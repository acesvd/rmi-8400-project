from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = STORAGE_DIR / "uploads"
ARTIFACT_DIR = STORAGE_DIR / "artifacts"
DB_PATH = Path(os.getenv("APPEALS_DB_PATH", BASE_DIR / "storage" / "appeals_os.db"))

def _normalize_ollama_base_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        return "http://localhost:11434"
    # Accept either host form (https://ollama.com) or API form (https://ollama.com/api).
    if value.endswith("/api"):
        return value[:-4]
    return value


OLLAMA_BASE_URL = _normalize_ollama_base_url(os.getenv("APPEALS_OLLAMA_BASE_URL", "http://localhost:11434"))
OLLAMA_API_KEY = (
    os.getenv("APPEALS_OLLAMA_API_KEY")
    or os.getenv("OLLAMA_API_KEY")
    or ""
).strip()
OLLAMA_CHAT_MODEL = os.getenv("APPEALS_OLLAMA_CHAT_MODEL", "llama3.1")
OLLAMA_EXTRACT_MODEL = os.getenv("APPEALS_OLLAMA_EXTRACT_MODEL", OLLAMA_CHAT_MODEL)
OLLAMA_LETTER_MODEL = os.getenv("APPEALS_OLLAMA_LETTER_MODEL", OLLAMA_CHAT_MODEL)
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("APPEALS_OLLAMA_TIMEOUT", "180"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
