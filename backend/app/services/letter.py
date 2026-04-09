from __future__ import annotations

import re
from datetime import datetime, timezone
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


def _reason_label(raw: str) -> str:
    return str(raw or "unknown").replace("_", " ").replace("-", " ").strip().title()


def _reason_default_quote(label: str) -> str:
    normalized = str(label or "").strip().lower()
    defaults = {
        "medical_necessity": "The payer determined the requested service did not meet medical necessity criteria.",
        "prior_authorization": "The payer indicated prior authorization requirements were not met.",
        "coding_billing": "The payer cited coding or documentation issues affecting claim adjudication.",
        "administrative": "The payer cited administrative criteria as the basis for denial.",
        "out_of_network": "The payer indicated network coverage constraints for the requested service.",
    }
    return defaults.get(normalized, "The payer identified this issue as part of the denial rationale.")


def _looks_low_quality_letter(text: str) -> bool:
    content = (text or "").strip()
    if len(content.split()) < 110:
        return True

    lower = content.lower()
    placeholder_markers = [
        "[your name]",
        "[your title]",
        "[your organization]",
        "lorem ipsum",
        "citation markers",
    ]
    if any(marker in lower for marker in placeholder_markers):
        return True

    # Markdown-heavy outputs typically look poor when converted to PDF for demos.
    if content.count("**") >= 4 or re.search(r"(?m)^#{1,6}\s", content):
        return True

    return False


def _collect_supporting_docs(citations: list[dict[str, Any]], reasons: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        citation = reason.get("citation") or {}
        name = str(citation.get("file_name") or "").strip()
        if name and name not in seen:
            ordered.append(name)
            seen.add(name)
    for c in citations:
        name = str(c.get("file_name") or "").strip()
        if name and name not in seen:
            ordered.append(name)
            seen.add(name)
    return ordered


def _build_letter_template(case_row: dict[str, Any], extraction: dict[str, Any], citations: list[dict[str, Any]], style: str) -> str:
    case_json = extraction.get("case_json") or {}
    ids = case_json.get("identifiers") or {}
    parties = case_json.get("parties") or {}
    reasons = case_json.get("denial_reasons") or []
    deadlines = case_json.get("deadlines") or []
    payer = case_json.get("payer", "unknown")
    patient_name = parties.get("patient_name", "the member")
    claimant_name = parties.get("claimant_name") or patient_name
    claim_number = ids.get("claim_number", "unknown")
    member_id = ids.get("member_id", "unknown")
    auth_number = ids.get("auth_number", "unknown")
    deadline_values = [str(d.get("value") or "").strip() for d in deadlines if str(d.get("value") or "").strip()]
    deadline_text = ", ".join(deadline_values) if deadline_values else "not specified in extracted data"
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    reason_lines: list[str] = []
    for reason in reasons:
        citation = reason.get("citation") or {}
        ref = f"{citation.get('file_name', 'document')} p.{citation.get('page_number', '?')}"
        raw_quote = str(reason.get("supporting_quote") or "").strip()
        quote = _short(raw_quote, 320) if raw_quote else _reason_default_quote(str(reason.get("label") or ""))
        if len(quote) < 32:
            quote = _reason_default_quote(str(reason.get("label") or ""))
        reason_lines.append(f"- {_reason_label(reason.get('label', 'unknown'))}: {quote} ({ref})")

    if not reason_lines:
        reason_lines.append("- Denial reason was not confidently extracted; manual review requested.")

    doc_names = _collect_supporting_docs(citations, reasons)
    if not doc_names:
        doc_names = ["No supporting documents were identified from retrieval."]

    concise_paragraph = (
        "This appeal requests prompt reconsideration of the denial based on the submitted records "
        "and the plan's medical necessity and authorization criteria."
    )
    formal_paragraph = (
        "I am writing to formally appeal the denial of the above claim and request full reconsideration. "
        "Based on the denial notice and submitted clinical information, we believe the determination should "
        "be reversed and the requested service approved."
    )

    body = [
        "Formal Claim Appeal Letter",
        "",
        f"Date: {today}",
        "To: Appeals Department",
        str(payer),
        "",
        "Re: Request for Reconsideration of Claim Denial",
        f"Case ID: {case_row['case_id']}",
        f"Claim Number: {claim_number}",
        f"Member ID: {member_id}",
        f"Authorization Number: {auth_number}",
        f"Patient: {patient_name}",
        f"Claimant: {claimant_name}",
        "",
        "Appeals Department,",
        "",
        concise_paragraph if style == "concise" else formal_paragraph,
        "",
        "Denial Basis Cited:",
        *reason_lines,
        "",
        "Requested Resolution:",
        "- Overturn the denial and approve the requested service.",
        "- Reprocess the related claim promptly based on the complete submitted record.",
        "- Provide a written determination and rationale after reconsideration.",
        "",
        "Supporting Documentation Submitted:",
        *[f"- {name}" for name in doc_names],
        "",
        f"Appeal Deadline (extracted): {deadline_text}.",
        "",
        "Thank you for your review and prompt attention to this appeal.",
        "",
        "Sincerely,",
        str(claimant_name),
        "Generated with ClaimRight appeal support tools",
        "",
        "Disclaimer: This draft is informational support and not legal or medical advice.",
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

    case_json = extraction.get("case_json") or {}
    ids = case_json.get("identifiers") or {}
    parties = case_json.get("parties") or {}
    reasons = case_json.get("denial_reasons") or []
    brief_reasons = [
        {
            "label": r.get("label"),
            "supporting_quote": _short(str(r.get("supporting_quote") or ""), 260),
            "citation": r.get("citation"),
        }
        for r in reasons[:5]
    ]

    system_prompt = (
        "You are an insurance claims appeal drafting assistant. "
        "Write a realistic, professional appeal letter in plain text (NOT markdown). "
        "Do not invent facts. If missing, explicitly state unknown. "
        "Keep tone neutral and respectful. Include source markers inline like '(file_name p.X)'. "
        "Do not include placeholders such as [Your Name], [Your Title], or template instructions. "
        "Use this structure: heading/date, addressee, case identifiers, appeal narrative, "
        "denial basis bullets, requested resolution bullets, supporting documents, signature, disclaimer."
    )

    user_prompt = (
        f"Draft style: {style}\n"
        f"Case:\n{dump_json({'case_id': case_row.get('case_id'), 'title': case_row.get('title')})}\n\n"
        f"Key identifiers:\n{dump_json(ids)}\n\n"
        f"Parties:\n{dump_json(parties)}\n\n"
        f"Payer:\n{dump_json({'payer': case_json.get('payer', 'unknown')})}\n\n"
        f"Denial reasons:\n{dump_json(brief_reasons)}\n\n"
        f"Evidence:\n{dump_json(evidence)}\n\n"
        "Return plain text only."
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
    letter_md = ""
    try:
        letter_md = _build_letter_llm(
            case_row=dict(case_row),
            extraction=extraction,
            citations=citations,
            style=style,
        )
        if not letter_md.strip():
            raise RuntimeError("Empty LLM response")
        if _looks_low_quality_letter(letter_md):
            raise RuntimeError("LLM letter failed quality checks")
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
