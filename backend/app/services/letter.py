from __future__ import annotations

from typing import Any

from ..config import ARTIFACT_DIR, OLLAMA_LETTER_MODEL
from .case_extraction import latest_case_extraction
from .llm import OllamaClient
from .retrieval import retrieve_case_chunks
from .utils import dump_json, new_id, utc_now_iso


def _next_version(conn, *, case_id: str, artifact_type: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM artifacts WHERE case_id = ? AND type = ?",
        (case_id, artifact_type),
    ).fetchone()
    return int(row["v"] or 0) + 1


def _short(text: str, n: int = 220) -> str:
    text = " ".join((text or "").split())
    return text[:n] + ("..." if len(text) > n else "")


def _build_letter_template(case_row: dict[str, Any], extraction: dict[str, Any], citations: list[dict[str, Any]], style: str) -> str:
    case_json = extraction.get("case_json") or {}
    ids = case_json.get("identifiers") or {}
    parties = case_json.get("parties") or {}
    reasons = case_json.get("denial_reasons") or []
    payer = case_json.get("payer", "unknown")
    patient_name = parties.get("patient_name", "unknown")

    tone_line = "This is a concise appeal summary." if style == "concise" else "This appeal requests full reconsideration based on supporting documentation."

    reason_lines = []
    for reason in reasons:
        citation = reason.get("citation") or {}
        ref = f"{citation.get('file_name', 'document')} p.{citation.get('page_number', '?')}"
        reason_lines.append(f"- {reason.get('label', 'unknown').replace('_', ' ').title()}: {reason.get('supporting_quote', '')} ({ref})")

    if not reason_lines:
        reason_lines.append("- Denial reason was not confidently extracted; manual review requested.")

    evidence_lines = []
    for i, c in enumerate(citations, start=1):
        evidence_lines.append(
            f"{i}. {_short(c.get('text', ''))} ({c.get('file_name', 'document')} p.{c.get('page_number', '?')})"
        )

    body = [
        "# Appeal Letter Draft",
        "",
        f"Case ID: {case_row['case_id']}",
        f"Patient: {patient_name}",
        f"Payer: {payer}",
        f"Claim #: {ids.get('claim_number', 'unknown')}",
        f"Auth #: {ids.get('auth_number', 'unknown')}",
        "",
        "To Whom It May Concern,",
        "",
        tone_line,
        "",
        "## Basis for Appeal",
        *reason_lines,
        "",
        "## Requested Action",
        "Please overturn the denial and reprocess the claim based on the attached documentation.",
        "",
        "## Supporting Evidence",
        *(evidence_lines or ["No retrieval evidence available; manual evidence review required."]),
        "",
        "Sincerely,",
        "Appeals Support System",
    ]

    return "\n".join(body)


def _build_letter_llm(
    *,
    case_row: dict[str, Any],
    extraction: dict[str, Any],
    citations: list[dict[str, Any]],
    style: str,
) -> str:
    client = OllamaClient()
    if not client.is_available():
        raise RuntimeError("Ollama unavailable")

    evidence = [
        {
            "file_name": c.get("file_name"),
            "document_id": c.get("document_id"),
            "page_number": c.get("page_number"),
            "snippet": _short(c.get("text", ""), 420),
        }
        for c in citations
    ]

    system_prompt = (
        "You are an insurance claims appeal drafting assistant. "
        "Write a professional appeal letter in markdown using only supplied case data and evidence. "
        "Do not invent facts. If missing, explicitly state unknown. "
        "Keep tone neutral and respectful. Include citation markers inline like '(file_name p.X)'. "
        "Add one-line disclaimer: informational support, not legal/medical advice."
    )

    user_prompt = (
        f"Draft style: {style}\n"
        f"Case:\n{dump_json({'case_id': case_row.get('case_id'), 'title': case_row.get('title')})}\n\n"
        f"Extraction:\n{dump_json(extraction.get('case_json') or {})}\n\n"
        f"Evidence:\n{dump_json(evidence)}\n\n"
        "Return markdown only."
    )

    return client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=OLLAMA_LETTER_MODEL,
        temperature=0.15,
    )


def generate_letter_artifact(conn, *, case_id: str, style: str = "formal") -> dict[str, Any]:
    case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case_row:
        raise ValueError("Case not found")

    extraction = latest_case_extraction(conn, case_id)
    if not extraction:
        raise ValueError("No case extraction found. Run /cases/{case_id}/extract first.")

    reasons = extraction.get("case_json", {}).get("denial_reasons") or []
    query = "appeal denial " + " ".join(r.get("label", "") for r in reasons)
    citations = retrieve_case_chunks(conn, case_id=case_id, query=query, top_k=8)

    generation_mode = "template_fallback"
    llm_error = None
    try:
        letter_md = _build_letter_llm(
            case_row=dict(case_row),
            extraction=extraction,
            citations=citations,
            style=style,
        )
        if not letter_md.strip():
            raise RuntimeError("Empty LLM response")
        generation_mode = "ollama"
    except Exception as exc:
        llm_error = str(exc)
        letter_md = _build_letter_template(dict(case_row), extraction, citations, style)

    version = _next_version(conn, case_id=case_id, artifact_type="letter")
    artifact_id = new_id("art")
    created_at = utc_now_iso()

    case_dir = ARTIFACT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    file_path = case_dir / f"letter_v{version}.md"
    file_path.write_text(letter_md, encoding="utf-8")

    metadata = {
        "citations": [
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("document_id"),
                "file_name": c.get("file_name"),
                "page_number": c.get("page_number"),
                "snippet": _short(c.get("text", ""), 300),
                "score": c.get("score"),
            }
            for c in citations
        ],
        "style": style,
        "generation_mode": generation_mode,
        "llm_error": llm_error,
    }

    conn.execute(
        """
        INSERT INTO artifacts (artifact_id, case_id, type, version, storage_path, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            case_id,
            "letter",
            version,
            str(file_path),
            dump_json(metadata),
            created_at,
        ),
    )

    return {
        "artifact_id": artifact_id,
        "case_id": case_id,
        "type": "letter",
        "version": version,
        "storage_path": str(file_path),
        "metadata": metadata,
        "created_at": created_at,
        "content": letter_md,
    }
