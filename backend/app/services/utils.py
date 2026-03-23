from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=True)


def safe_filename(name: str) -> str:
    raw = Path(name).name
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "-", "_"}) or "upload.bin"
