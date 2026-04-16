from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import ARTIFACT_DIR, UPLOAD_DIR
from .database import get_conn, init_db
from .schemas import (
    ChatRequest,
    CaseCreate,
    CaseExtractionManualUpdate,
    EventCreate,
    LetterRequest,
    PacketRequest,
    TaskUpdate,
)
from .services.assistant_chat import answer_case_question
from .services.case_extraction import build_case_json, latest_case_extraction, save_case_extraction
from .services.denial_outcomes import get_appealability
from .services.document_processing import process_document
from .services.letter import generate_letter_artifact
from .services.llm import OllamaClient
from .services.packet import generate_packet_artifact
from .services.tasks import generate_tasks
from .services.utils import new_id, parse_json, safe_filename, utc_now_iso

APP_NAME = "Claims Appeal OS API"
APP_VERSION = "0.1.0"

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


def _row_to_case(row) -> dict[str, Any]:
    return {
        "case_id": row["case_id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_doc(row) -> dict[str, Any]:
    return {
        "document_id": row["document_id"],
        "case_id": row["case_id"],
        "type": row["type"],
        "filename": row["filename"],
        "storage_path": row["storage_path"],
        "processed_status": row["processed_status"],
        "uploaded_at": row["uploaded_at"],
    }


def _row_to_task(row) -> dict[str, Any]:
    return {
        "task_id": row["task_id"],
        "case_id": row["case_id"],
        "title": row["title"],
        "description": row["description"],
        "owner": row["owner"],
        "due_date": row["due_date"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _row_to_artifact(row) -> dict[str, Any]:
    return {
        "artifact_id": row["artifact_id"],
        "case_id": row["case_id"],
        "type": row["type"],
        "version": row["version"],
        "storage_path": row["storage_path"],
        "metadata": parse_json(row["metadata"], {}),
        "created_at": row["created_at"],
    }


def _require_case(conn, case_id: str):
    row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


def _mark_document_failed(conn, *, document_id: str, error: Exception) -> str:
    error_message = str(error).strip() or error.__class__.__name__
    conn.execute(
        "UPDATE documents SET processed_status = ? WHERE document_id = ?",
        (f"failed: {error_message}", document_id),
    )
    return error_message


def _normalize_text(value: str | None, *, default: str = "unknown") -> str:
    text = (value or "").strip()
    return text if text else default


def _normalize_csv_like(values: list[str] | None, *, lower: bool = False) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for token in str(raw).replace("\n", ",").split(","):
            item = token.strip()
            if not item:
                continue
            if lower:
                item = item.lower()
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def _normalize_reason_label(label: str) -> str:
    clean = str(label).strip().lower().replace("-", "_").replace(" ", "_")
    allowed = {"administrative", "medical_necessity", "prior_authorization", "coding_billing", "out_of_network"}
    if clean in allowed:
        return clean
    return "administrative"


def _manual_reason_item(label: str) -> dict[str, Any]:
    normalized = _normalize_reason_label(label)
    return {
        "label": normalized,
        "keyword": "manual_entry",
        "supporting_quote": "Manually entered by user.",
        "citation": {
            "document_id": "manual_entry",
            "file_name": "Manual Entry",
            "page_number": 0,
        },
    }


def _manual_deadline_item(value: str) -> dict[str, Any]:
    deadline_value = _normalize_text(value, default="")
    return {
        "value": deadline_value,
        "citation": {
            "document_id": "manual_entry",
            "file_name": "Manual Entry",
            "page_number": 0,
            "quote": "Manually entered by user.",
        },
    }


def _scalar_value(row: Any) -> Any:
    if row is None:
        return None
    try:
        return row[0]
    except Exception:
        pass
    if isinstance(row, dict):
        for value in row.values():
            return value
    keys = getattr(row, "keys", None)
    if callable(keys):
        key_list = list(keys())
        if key_list:
            return row[key_list[0]]
    return None


def _case_fingerprint_for_appealability(conn, *, case_id: str, extraction: dict[str, Any]) -> str:
    case_row = _require_case(conn, case_id)

    docs_count = _scalar_value(conn.execute("SELECT COUNT(*) AS c FROM documents WHERE case_id = ?", (case_id,)).fetchone()) or 0
    docs_latest = _scalar_value(
        conn.execute("SELECT COALESCE(MAX(uploaded_at), '') AS latest FROM documents WHERE case_id = ?", (case_id,)).fetchone()
    ) or ""

    tasks_count = _scalar_value(conn.execute("SELECT COUNT(*) AS c FROM tasks WHERE case_id = ?", (case_id,)).fetchone()) or 0
    tasks_latest = _scalar_value(
        conn.execute("SELECT COALESCE(MAX(created_at), '') AS latest FROM tasks WHERE case_id = ?", (case_id,)).fetchone()
    ) or ""

    artifacts_count = _scalar_value(conn.execute("SELECT COUNT(*) AS c FROM artifacts WHERE case_id = ?", (case_id,)).fetchone()) or 0
    artifacts_latest = _scalar_value(
        conn.execute("SELECT COALESCE(MAX(created_at), '') AS latest FROM artifacts WHERE case_id = ?", (case_id,)).fetchone()
    ) or ""

    events_count = _scalar_value(conn.execute("SELECT COUNT(*) AS c FROM events WHERE case_id = ?", (case_id,)).fetchone()) or 0
    events_latest = _scalar_value(
        conn.execute("SELECT COALESCE(MAX(timestamp), '') AS latest FROM events WHERE case_id = ?", (case_id,)).fetchone()
    ) or ""

    payload = {
        "case_id": case_id,
        "case_updated_at": case_row["updated_at"],
        "extraction_id": extraction.get("extraction_id"),
        "extraction_created_at": extraction.get("created_at"),
        "extraction_mode": extraction.get("mode"),
        "documents": {"count": int(docs_count), "latest": str(docs_latest)},
        "tasks": {"count": int(tasks_count), "latest": str(tasks_latest)},
        "artifacts": {"count": int(artifacts_count), "latest": str(artifacts_latest)},
        "events": {"count": int(events_count), "latest": str(events_latest)},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_appealability_cache(
    conn,
    *,
    case_id: str,
    fingerprint: str,
) -> tuple[dict[str, Any], bool, str] | None:
    row = conn.execute(
        "SELECT fingerprint, result_json, computed_at FROM appealability_cache WHERE case_id = ?",
        (case_id,),
    ).fetchone()
    if not row:
        return None

    cached_data = parse_json(row["result_json"], None)
    if not isinstance(cached_data, dict):
        return None

    cached_data["case_id"] = case_id
    is_fresh = str(row["fingerprint"]) == fingerprint
    computed_at = str(row["computed_at"] or "")
    return cached_data, is_fresh, computed_at


def _save_appealability_cache(
    conn,
    *,
    case_id: str,
    fingerprint: str,
    result: dict[str, Any],
) -> str:
    computed_at = utc_now_iso()
    conn.execute("DELETE FROM appealability_cache WHERE case_id = ?", (case_id,))
    conn.execute(
        """
        INSERT INTO appealability_cache (case_id, fingerprint, result_json, computed_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            case_id,
            fingerprint,
            json.dumps(result, ensure_ascii=True, separators=(",", ":")),
            computed_at,
        ),
    )
    return computed_at


@app.get("/health")
def health() -> dict[str, Any]:
    client = OllamaClient()
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
        "ollama_available": client.is_available(),
    }


@app.post("/cases")
def create_case(body: CaseCreate) -> dict[str, Any]:
    case_id = new_id("case")
    now = utc_now_iso()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cases (case_id, title, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (case_id, body.title.strip(), "draft", now, now),
        )
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return _row_to_case(row)


@app.get("/cases")
def list_cases() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
    return [_row_to_case(r) for r in rows]


@app.delete("/cases/{case_id}")
def delete_case(case_id: str) -> dict[str, Any]:
    upload_case_dir = UPLOAD_DIR / case_id
    artifact_case_dir = ARTIFACT_DIR / case_id

    with get_conn() as conn:
        case_row = _require_case(conn, case_id)
        conn.execute("DELETE FROM cases WHERE case_id = ?", (case_id,))

    shutil.rmtree(upload_case_dir, ignore_errors=True)
    shutil.rmtree(artifact_case_dir, ignore_errors=True)

    return {
        "deleted": True,
        "case_id": case_id,
        "title": case_row["title"],
    }


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        case_row = _require_case(conn, case_id)

        docs = conn.execute(
            "SELECT * FROM documents WHERE case_id = ? ORDER BY uploaded_at DESC",
            (case_id,),
        ).fetchall()
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE case_id = ? ORDER BY created_at",
            (case_id,),
        ).fetchall()
        artifacts = conn.execute(
            "SELECT * FROM artifacts WHERE case_id = ? ORDER BY type, version DESC",
            (case_id,),
        ).fetchall()
        events = conn.execute(
            "SELECT * FROM events WHERE case_id = ? ORDER BY timestamp DESC",
            (case_id,),
        ).fetchall()

        extraction = latest_case_extraction(conn, case_id)

    return {
        "case": _row_to_case(case_row),
        "documents": [_row_to_doc(r) for r in docs],
        "extraction": extraction,
        "tasks": [_row_to_task(r) for r in tasks],
        "artifacts": [_row_to_artifact(r) for r in artifacts],
        "events": [dict(r) for r in events],
    }


@app.post("/cases/{case_id}/documents")
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    auto_process: bool = Form(True),
) -> dict[str, Any]:
    doc_type = doc_type.strip().lower()
    if not doc_type:
        raise HTTPException(status_code=400, detail="doc_type is required")

    with get_conn() as conn:
        _require_case(conn, case_id)

        document_id = new_id("doc")
        now = utc_now_iso()
        filename = safe_filename(file.filename or f"{document_id}.bin")

        case_dir = UPLOAD_DIR / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        storage_path = case_dir / f"{document_id}_{filename}"
        content = await file.read()
        storage_path.write_bytes(content)

        conn.execute(
            """
            INSERT INTO documents (document_id, case_id, type, filename, storage_path, processed_status, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                case_id,
                doc_type,
                filename,
                str(storage_path),
                "uploaded",
                now,
            ),
        )

        conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
            ("waiting_on_docs", now, case_id),
        )

        process_summary = None
        if auto_process:
            try:
                process_summary = process_document(
                    conn,
                    case_id=case_id,
                    document_id=document_id,
                    storage_path=str(storage_path),
                )
            except Exception as exc:
                process_summary = {
                    "pages": 0,
                    "chunks": 0,
                    "error": _mark_document_failed(conn, document_id=document_id, error=exc),
                }

        row = conn.execute("SELECT * FROM documents WHERE document_id = ?", (document_id,)).fetchone()

    payload = _row_to_doc(row)
    if process_summary is not None:
        payload["process_summary"] = process_summary
    return payload


@app.get("/cases/{case_id}/documents")
def list_documents(case_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        rows = conn.execute(
            "SELECT * FROM documents WHERE case_id = ? ORDER BY uploaded_at DESC",
            (case_id,),
        ).fetchall()
    return [_row_to_doc(r) for r in rows]


@app.post("/cases/{case_id}/process")
def process_case_docs(case_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        docs = conn.execute(
            "SELECT document_id, storage_path FROM documents WHERE case_id = ?",
            (case_id,),
        ).fetchall()

        results: list[dict[str, Any]] = []
        for doc in docs:
            try:
                summary = process_document(
                    conn,
                    case_id=case_id,
                    document_id=doc["document_id"],
                    storage_path=doc["storage_path"],
                )
            except Exception as exc:
                summary = {
                    "pages": 0,
                    "chunks": 0,
                    "error": _mark_document_failed(conn, document_id=doc["document_id"], error=exc),
                }
            results.append({"document_id": doc["document_id"], **summary})

    return {"case_id": case_id, "processed_documents": results}


@app.post("/cases/{case_id}/extract")
def run_case_extraction(case_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        case_json, warnings, mode = build_case_json(conn, case_id)
        saved = save_case_extraction(conn, case_id=case_id, case_json=case_json, warnings=warnings, mode=mode)
        conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
            ("ready", utc_now_iso(), case_id),
        )
    return saved


@app.get("/cases/{case_id}/extract")
def get_case_extraction(case_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        extraction = latest_case_extraction(conn, case_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="No extraction found")
    return extraction


@app.patch("/cases/{case_id}/extract")
def update_case_extraction(case_id: str, body: CaseExtractionManualUpdate) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        extraction = latest_case_extraction(conn, case_id)
        if not extraction:
            raise HTTPException(status_code=400, detail="Run extraction first")

        current = extraction.get("case_json") or {}
        current_identifiers = current.get("identifiers") if isinstance(current.get("identifiers"), dict) else {}
        current_parties = current.get("parties") if isinstance(current.get("parties"), dict) else {}
        fields_set = set(getattr(body, "model_fields_set", set()))

        normalized_reasons = _normalize_csv_like(body.denial_reasons, lower=False)
        normalized_deadlines = _normalize_csv_like(body.deadlines, lower=False)
        normalized_channels = _normalize_csv_like(body.submission_channels, lower=True)
        normalized_docs = _normalize_csv_like(body.requested_documents, lower=True)

        payer = (
            _normalize_text(body.payer, default=current.get("payer", "unknown"))
            if "payer" in fields_set
            else _normalize_text(current.get("payer"), default="unknown")
        )
        plan_type = (
            _normalize_text(body.plan_type, default=current.get("plan_type", "unknown"))
            if "plan_type" in fields_set
            else _normalize_text(current.get("plan_type"), default="unknown")
        )

        claim_number = (
            _normalize_text(body.claim_number, default=current_identifiers.get("claim_number", "unknown"))
            if "claim_number" in fields_set
            else _normalize_text(current_identifiers.get("claim_number"), default="unknown")
        )
        auth_number = (
            _normalize_text(body.auth_number, default=current_identifiers.get("auth_number", "unknown"))
            if "auth_number" in fields_set
            else _normalize_text(current_identifiers.get("auth_number"), default="unknown")
        )
        member_id = (
            _normalize_text(body.member_id, default=current_identifiers.get("member_id", "unknown"))
            if "member_id" in fields_set
            else _normalize_text(current_identifiers.get("member_id"), default="unknown")
        )

        patient_name = (
            _normalize_text(body.patient_name, default=current_parties.get("patient_name", "unknown"))
            if "patient_name" in fields_set
            else _normalize_text(current_parties.get("patient_name"), default="unknown")
        )
        claimant_name = (
            _normalize_text(body.claimant_name, default=current_parties.get("claimant_name", "unknown"))
            if "claimant_name" in fields_set
            else _normalize_text(current_parties.get("claimant_name"), default="unknown")
        )

        updated_case_json = {
            **current,
            "payer": payer,
            "plan_type": plan_type,
            "identifiers": {
                "claim_number": claim_number,
                "auth_number": auth_number,
                "member_id": member_id,
            },
            "parties": {
                "patient_name": patient_name,
                "claimant_name": claimant_name,
            },
            "denial_reasons": (
                [_manual_reason_item(reason) for reason in normalized_reasons]
                if "denial_reasons" in fields_set
                else current.get("denial_reasons", [])
            ),
            "deadlines": (
                [_manual_deadline_item(deadline) for deadline in normalized_deadlines]
                if "deadlines" in fields_set
                else current.get("deadlines", [])
            ),
            "submission_channels": (
                normalized_channels if "submission_channels" in fields_set else current.get("submission_channels", [])
            ),
            "requested_documents": (
                normalized_docs if "requested_documents" in fields_set else current.get("requested_documents", [])
            ),
        }

        existing_warnings = extraction.get("warnings") or []
        manual_warning = "Case extraction includes manual user edits."
        warnings = [manual_warning, *[w for w in existing_warnings if w != manual_warning]]

        saved = save_case_extraction(
            conn,
            case_id=case_id,
            case_json=updated_case_json,
            warnings=warnings,
            mode="manual_edit",
        )
        conn.execute("UPDATE cases SET updated_at = ? WHERE case_id = ?", (utc_now_iso(), case_id))

    return saved


@app.post("/cases/{case_id}/tasks/generate")
def generate_case_tasks(case_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        extraction = latest_case_extraction(conn, case_id)
        if not extraction:
            raise HTTPException(status_code=400, detail="Run extraction first")
        tasks = generate_tasks(conn, case_id=case_id, case_json=extraction["case_json"])
    return tasks


@app.get("/cases/{case_id}/tasks")
def list_tasks(case_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        rows = conn.execute("SELECT * FROM tasks WHERE case_id = ? ORDER BY created_at", (case_id,)).fetchall()
    return [_row_to_task(r) for r in rows]


@app.patch("/cases/{case_id}/tasks/{task_id}")
def update_task(case_id: str, task_id: str, body: TaskUpdate) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        row = conn.execute(
            "SELECT * FROM tasks WHERE case_id = ? AND task_id = ?",
            (case_id, task_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        conn.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?",
            (body.status, task_id),
        )
        updated = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    return _row_to_task(updated)


@app.post("/cases/{case_id}/letter")
def create_letter(case_id: str, body: LetterRequest) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        artifact = generate_letter_artifact(conn, case_id=case_id, style=body.style)
        payload = {
            k: artifact[k]
            for k in ["artifact_id", "case_id", "type", "version", "storage_path", "metadata", "created_at"]
        }
        payload["preview"] = artifact["content"]
    return payload


@app.post("/cases/{case_id}/packet")
def create_packet(case_id: str, body: PacketRequest) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        artifact = generate_packet_artifact(
            conn,
            case_id=case_id,
            include_uploaded_pdfs=body.include_uploaded_pdfs,
        )
    return artifact


@app.post("/chat")
def general_chat(body: ChatRequest) -> dict[str, Any]:
    warning = (
        "This is general guidance without case-specific context. "
        "Create or select a case for personalized appeal support."
    )
    client = OllamaClient()
    if not client.is_available():
        return {
            "answer": (
                "I can help with general claim appeal questions, but the LLM service is currently unavailable. "
                "Please try again shortly or switch to a case-specific chat."
            ),
            "sources": [],
            "mode": "general_fallback",
            "warning": warning,
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are ClaimRight's general assistant for denied health insurance claims. "
                "Provide concise, practical educational guidance in plain language. "
                "Do not invent case facts. Mention when users should seek clinician/legal help."
            ),
        },
        {"role": "user", "content": body.question.strip()},
    ]

    try:
        answer = client.chat(messages=messages, model=client.config.chat_model, temperature=0.2)
    except Exception as exc:
        return {
            "answer": (
                "I couldn't generate a general response right now. "
                f"Please try again. Error: {exc}"
            ),
            "sources": [],
            "mode": "general_error",
            "warning": warning,
        }

    if not answer:
        answer = "I did not find enough information to answer that. Please rephrase and try again."

    return {
        "answer": answer,
        "sources": [],
        "mode": "general",
        "warning": warning,
    }


@app.post("/cases/{case_id}/chat")
def case_chat(case_id: str, body: ChatRequest) -> dict[str, Any]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        response = answer_case_question(conn, case_id=case_id, question=body.question)
    return response


@app.get("/cases/{case_id}/artifacts")
def list_artifacts(case_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE case_id = ? ORDER BY type, version DESC",
            (case_id,),
        ).fetchall()
    return [_row_to_artifact(r) for r in rows]


@app.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Artifact not found")

    path = Path(row["storage_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")

    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/markdown"
    return FileResponse(path=path, media_type=media_type, filename=path.name)


@app.post("/cases/{case_id}/events")
def add_event(case_id: str, body: EventCreate) -> dict[str, Any]:
    with get_conn() as conn:
        case_row = _require_case(conn, case_id)
        event_id = new_id("evt")
        conn.execute(
            """
            INSERT INTO events (event_id, case_id, type, timestamp, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, case_id, body.type, body.timestamp, body.notes.strip()),
        )

        new_status = case_row["status"]
        if body.type == "submitted":
            new_status = "submitted"
        elif body.type == "decision":
            notes_l = body.notes.lower()
            if "approved" in notes_l:
                new_status = "resolved"
            elif "denied" in notes_l:
                new_status = "ready"

        conn.execute(
            "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
            (new_status, utc_now_iso(), case_id),
        )

        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    return dict(row)


@app.get("/cases/{case_id}/events")
def list_events(case_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        _require_case(conn, case_id)
        rows = conn.execute(
            "SELECT * FROM events WHERE case_id = ? ORDER BY timestamp DESC",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- A1: Appealability Score ---


@app.get("/cases/{case_id}/appealability")
def get_case_appealability(
    case_id: str,
    recompute: bool = False,
    cached_only: bool = False,
) -> dict[str, Any]:
    """Return cached or newly computed appealability score for a case.

    Requires extraction to have been run first (POST /cases/{case_id}/extract).
    Uses S1 (IMR overturn rates) for R1 denials and S3 (insurer benchmark) for R2 denials.
    By default, returns saved score if present. Use `recompute=true` to force recomputation.
    Use `cached_only=true` to fetch only previously saved results.
    """
    with get_conn() as conn:
        _require_case(conn, case_id)
        extraction = latest_case_extraction(conn, case_id)

        if not extraction:
            raise HTTPException(
                status_code=400,
                detail="No extraction found. Run POST /cases/{case_id}/extract first.",
            )

        fingerprint = _case_fingerprint_for_appealability(conn, case_id=case_id, extraction=extraction)

        if not recompute:
            cached = _load_appealability_cache(conn, case_id=case_id, fingerprint=fingerprint)
            if cached:
                payload, is_fresh, computed_at = cached
                payload["_cache"] = {
                    "hit": True,
                    "fresh": is_fresh,
                    "computed_at": computed_at,
                }
                return payload

            if cached_only:
                raise HTTPException(
                    status_code=404,
                    detail="No saved appealability score for this case yet.",
                )

        case_json = extraction.get("case_json", {})
        result = get_appealability(case_json)
        result["case_id"] = case_id
        computed_at = _save_appealability_cache(
            conn,
            case_id=case_id,
            fingerprint=fingerprint,
            result=result,
        )
        result["_cache"] = {
            "hit": False,
            "fresh": True,
            "computed_at": computed_at,
        }
        return result
