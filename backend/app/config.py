from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = STORAGE_DIR / "uploads"
ARTIFACT_DIR = STORAGE_DIR / "artifacts"
DB_PATH = Path(os.getenv("APPEALS_DB_PATH", BASE_DIR / "storage" / "appeals_os.db"))

OLLAMA_BASE_URL = os.getenv("APPEALS_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.getenv("APPEALS_OLLAMA_CHAT_MODEL", "llama3.1")
OLLAMA_EXTRACT_MODEL = os.getenv("APPEALS_OLLAMA_EXTRACT_MODEL", OLLAMA_CHAT_MODEL)
OLLAMA_LETTER_MODEL = os.getenv("APPEALS_OLLAMA_LETTER_MODEL", OLLAMA_CHAT_MODEL)
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("APPEALS_OLLAMA_TIMEOUT", "180"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)