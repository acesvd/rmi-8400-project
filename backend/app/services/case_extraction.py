from __future__ import annotations

import re
from typing import Any

from ..config import OLLAMA_EXTRACT_MODEL
from .llm import OllamaClient
from .utils import dump_json, new_id, parse_json, utc_now_iso

REASON_RULES: list[tuple[str, list[str]]] = [
    ("administrative", ["missing information", "incomplete", "administrative", "timely filing"]),
    ("medical_necessity", ["medical necessity", "not medically necessary", "investigational", "experimental"]),
    ("prior_authorization", ["prior authorization", "preauthorization", "pre-authorization"]),
    ("coding_billing", ["coding", "cpt", "icd", "billing", "modifier"]),
    ("out_of_network", ["out-of-network", "out of network", "balance bill", "non-contracted"]),
]

CLAIM_PATTERNS = [
    r"claim\s*(?:#|number|no\.?|num(?:ber)?)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{4,})",
    r"claim[:\s\-]+([A-Z0-9][A-Z0-9\-]{4,})",
]
AUTH_PATTERNS = [
    r"(?:auth(?:orization)?|preauth)\s*(?:#|number|no\.?|num(?:ber)?)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{4,})"
]
MEMBER_PATTERNS = [
    r"member\s*(?:id|#|number|no\.?|num(?:ber)?)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{4,})",
    r"subscriber\s*(?:id|#|number|no\.?|num(?:ber)?)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{4,})",
]
PAYER_PATTERNS = [r"(?:payer|insurance|insurer|plan):?\s*([A-Za-z0-9&\-\., ]{3,80})"]
NAME_PATTERNS = [
    r"(?:dear|doar)\s+([A-Z][A-Z\s'\-]{2,60})[,:\n]",
    r"(?:patient|member|subscriber|claimant)\s*(?:name)?\s*[:\-]?\s*([A-Za-z][A-Za-z\s'\-]{2,60})",
]
DEADLINE_PATTERNS = [
    r"(?:appeal|file)\s*(?:within|by)\s*(\d{1,2}/\d{1,2}/\d{2,4})",
    r"deadline\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})",
    r"within\s+(\d{1,3}\s+days?)",
]


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def _unique(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        val = str(item or "").strip()
        if not val:
            continue
        if val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _find_first(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            candidate = _norm(m.group(1))
            if any(ch.isdigit() for ch in candidate) or "-" in candidate:
                return candidate
    return None


def _ocr_normalize(text: str) -> str:
    text = text or ""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": "-",
        "\u2013": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _collect_doc_text(conn, case_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.document_id, d.type, d.filename, p.page_number, p.text
        FROM documents d
        LEFT JOIN doc_pages p ON p.document_id = d.document_id
        WHERE d.case_id = ?
        ORDER BY d.uploaded_at, p.page_number
        """,
        (case_id,),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "document_id": row["document_id"],
                "type": row["type"],
                "filename": row["filename"],
                "page_number": row["page_number"],
                "text": _ocr_normalize(row["text"] or ""),
            }
        )
    return out


def _looks_like_identifier(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) < 4:
        return False
    return any(ch.isdigit() for ch in text) or "-" in text


def _clean_name(value: Any) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ,:")
    if not text:
        return "unknown"
    if len(text) < 3 or len(text) > 60:
        return "unknown"
    if any(ch.isdigit() for ch in text):
        return "unknown"
    words = [w for w in text.split(" ") if w]
    if not words:
        return "unknown"
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def _find_name(text: str) -> str | None:
    for pattern in NAME_PATTERNS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = _clean_name(m.group(1))
        if candidate != "unknown":
            return candidate
    return None


def _extract_reasons(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    seen: set[str] = set()
    for label, keywords in REASON_RULES:
        for page in pages:
            text_l = (page["text"] or "").lower()
            for kw in keywords:
                idx = text_l.find(kw)
                if idx == -1:
                    continue
                if label in seen:
                    break
                quote = _norm(page["text"][max(idx - 80, 0): idx + len(kw) + 120])
                reasons.append(
                    {
                        "label": label,
                        "keyword": kw,
                        "supporting_quote": quote,
                        "citation": {
                            "document_id": page["document_id"],
                            "file_name": page["filename"],
                            "page_number": page["page_number"],
                        },
                    }
                )
                seen.add(label)
                break
    return reasons


def _extract_deadlines(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = set()
    for page in pages:
        text = page["text"] or ""
        for pattern in DEADLINE_PATTERNS:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                val = _norm(m.group(1))
                key = (val, page["document_id"], page["page_number"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    {
                        "value": val,
                        "citation": {
                            "document_id": page["document_id"],
                            "file_name": page["filename"],
                            "page_number": page["page_number"],
                            "quote": _norm(text[max(m.start() - 70, 0): m.end() + 70]),
                        },
                    }
                )
    return out


def _extract_channels(full_text: str) -> list[str]:
    channels = []
    text_l = full_text.lower()
    if "fax" in text_l:
        channels.append("fax")
    if "portal" in text_l or "online" in text_l:
        channels.append("portal")
    if "mail" in text_l or "address" in text_l:
        channels.append("mail")
    return channels


def _document_context_warnings(full_text: str) -> list[str]:
    text_l = full_text.lower()
    warnings: list[str] = []
    if (
        "thank you for applying" in text_l
        and "coverage" in text_l
        and "claim" not in text_l
        and "appeal" not in text_l
    ):
        warnings.append(
            "Uploaded text looks more like a coverage/application notice than a claim denial letter. Verify the source document."
        )
    return warnings


def _warnings_for_case_json(case_json: dict[str, Any], *, full_text: str) -> list[str]:
    warnings: list[str] = []
    identifiers = case_json.get("identifiers") or {}
    if identifiers.get("claim_number") in {None, "", "unknown"}:
        warnings.append("Claim number not found in uploaded text.")
    if not (case_json.get("deadlines") or []):
        warnings.append("No explicit appeal deadline found in uploaded text.")
    if not (case_json.get("denial_reasons") or []):
        warnings.append("No denial reason label confidently detected. Review denial letter manually.")
    warnings.extend(_document_context_warnings(full_text))
    return _unique(warnings)


def build_case_json_rule_based(conn, case_id: str) -> tuple[dict[str, Any], list[str]]:
    pages = _collect_doc_text(conn, case_id)
    full_text = "\n\n".join(p["text"] for p in pages if p["text"])

    claim_no = _find_first(CLAIM_PATTERNS, full_text)
    auth_no = _find_first(AUTH_PATTERNS, full_text)
    member_id = _find_first(MEMBER_PATTERNS, full_text)
    payer = _find_first(PAYER_PATTERNS, full_text)
    patient_name = _find_name(full_text)

    reasons = _extract_reasons(pages)
    deadlines = _extract_deadlines(pages)
    channels = _extract_channels(full_text)

    existing_doc_types = {
        row["type"]
        for row in conn.execute(
            "SELECT type FROM documents WHERE case_id = ?",
            (case_id,),
        ).fetchall()
    }

    required = ["denial_letter", "eob", "medical_records", "prior_auth"]
    missing = [doc_type for doc_type in required if doc_type not in existing_doc_types]

    case_json = {
        "payer": payer or "unknown",
        "plan_type": "unknown",
        "identifiers": {
            "claim_number": claim_no or "unknown",
            "auth_number": auth_no or "unknown",
            "member_id": member_id or "unknown",
        },
        "parties": {
            "patient_name": patient_name or "unknown",
            "claimant_name": patient_name or "unknown",
        },
        "denial_reasons": reasons,
        "deadlines": deadlines,
        "submission_channels": channels,
        "requested_documents": missing,
        "warnings": [],
    }

    warnings = _warnings_for_case_json(case_json, full_text=full_text)
    case_json["warnings"] = warnings
    return case_json, warnings


def _snippet_payload(pages: list[dict[str, Any]], limit: int = 24, max_chars: int = 1000) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue
        snippets.append(
            {
                "document_id": page.get("document_id"),
                "file_name": page.get("filename"),
                "page_number": page.get("page_number"),
                "text": text[:max_chars],
            }
        )
        if len(snippets) >= limit:
            break
    return snippets


def _llm_extract_case_json(client: OllamaClient, pages: list[dict[str, Any]]) -> dict[str, Any]:
    snippets = _snippet_payload(pages)
    if not snippets:
        raise ValueError("No extracted page text available for LLM extraction")

    prompt = (
        "You extract structured insurance claim appeal data from denial-related documents.\n"
        "Use ONLY the snippets provided. Never invent identifiers, deadlines, or citations.\n"
        "Return JSON only.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "payer": string,\n'
        '  "plan_type": string,\n'
        '  "identifiers": {"claim_number": string, "auth_number": string, "member_id": string},\n'
        '  "parties": {"patient_name": string, "claimant_name": string},\n'
        '  "denial_reasons": [\n'
        '    {"label": string, "supporting_quote": string, "citation": {"document_id": string, "file_name": string, "page_number": number}}\n'
        "  ],\n"
        '  "deadlines": [\n'
        '    {"value": string, "citation": {"document_id": string, "file_name": string, "page_number": number, "quote": string}}\n'
        "  ],\n"
        '  "submission_channels": [string],\n'
        '  "requested_documents": [string],\n'
        '  "warnings": [string]\n'
        "}\n\n"
        "Rules:\n"
        "- If unknown, use 'unknown' or []\n"
        "- labels should be one of: administrative, medical_necessity, prior_authorization, coding_billing, out_of_network\n"
        "- citations must refer to provided snippet metadata\n\n"
        f"Snippets:\n{dump_json(snippets)}"
    )

    return client.generate_json(
        prompt=prompt,
        model=OLLAMA_EXTRACT_MODEL,
        temperature=0.0,
    )


def _normalized_case_json(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    out = dict(fallback)

    out["payer"] = str(raw.get("payer") or fallback.get("payer") or "unknown")
    out["plan_type"] = str(raw.get("plan_type") or fallback.get("plan_type") or "unknown")

    ids_fallback = fallback.get("identifiers") or {}
    ids_raw = raw.get("identifiers") if isinstance(raw.get("identifiers"), dict) else {}
    claim_candidate = ids_raw.get("claim_number")
    auth_candidate = ids_raw.get("auth_number")
    member_candidate = ids_raw.get("member_id")
    out["identifiers"] = {
        "claim_number": str(claim_candidate if _looks_like_identifier(claim_candidate) else ids_fallback.get("claim_number") or "unknown"),
        "auth_number": str(auth_candidate if _looks_like_identifier(auth_candidate) else ids_fallback.get("auth_number") or "unknown"),
        "member_id": str(member_candidate if _looks_like_identifier(member_candidate) else ids_fallback.get("member_id") or "unknown"),
    }

    parties_fallback = fallback.get("parties") if isinstance(fallback.get("parties"), dict) else {}
    parties_raw = raw.get("parties") if isinstance(raw.get("parties"), dict) else {}
    patient_candidate = _clean_name(parties_raw.get("patient_name"))
    claimant_candidate = _clean_name(parties_raw.get("claimant_name"))
    fallback_patient = _clean_name(parties_fallback.get("patient_name"))
    fallback_claimant = _clean_name(parties_fallback.get("claimant_name"))
    out["parties"] = {
        "patient_name": patient_candidate if patient_candidate != "unknown" else fallback_patient,
        "claimant_name": claimant_candidate if claimant_candidate != "unknown" else (fallback_claimant if fallback_claimant != "unknown" else fallback_patient),
    }

    reasons = raw.get("denial_reasons") if isinstance(raw.get("denial_reasons"), list) else []
    reason_items = [r for r in reasons if isinstance(r, dict)]
    deduped_reasons: list[dict[str, Any]] = []
    seen_reasons: set[tuple[str, str, Any]] = set()
    for reason in reason_items:
        citation = reason.get("citation") if isinstance(reason.get("citation"), dict) else {}
        key = (
            str(reason.get("label") or "").strip(),
            str(reason.get("supporting_quote") or "").strip(),
            citation.get("page_number"),
        )
        if key in seen_reasons:
            continue
        seen_reasons.add(key)
        deduped_reasons.append(reason)
    out["denial_reasons"] = deduped_reasons or fallback.get("denial_reasons", [])

    deadlines = raw.get("deadlines") if isinstance(raw.get("deadlines"), list) else []
    out["deadlines"] = [d for d in deadlines if isinstance(d, dict)] or fallback.get("deadlines", [])

    sub_channels = raw.get("submission_channels") if isinstance(raw.get("submission_channels"), list) else []
    cleaned_channels = [str(c).strip() for c in sub_channels if str(c).strip() and str(c).strip().lower() != "unknown"]
    out["submission_channels"] = _unique(cleaned_channels) or fallback.get("submission_channels", [])

    req_docs = raw.get("requested_documents") if isinstance(raw.get("requested_documents"), list) else []
    cleaned_docs = [str(d).strip() for d in req_docs if str(d).strip() and str(d).strip().lower() != "unknown"]
    out["requested_documents"] = _unique(cleaned_docs) or fallback.get("requested_documents", [])

    warnings = raw.get("warnings") if isinstance(raw.get("warnings"), list) else []
    out["warnings"] = _unique([str(w) for w in warnings if str(w).strip() and str(w).strip().lower() != "unknown"])

    return out


def build_case_json(conn, case_id: str) -> tuple[dict[str, Any], list[str], str]:
    rule_case_json, rule_warnings = build_case_json_rule_based(conn, case_id)

    pages = _collect_doc_text(conn, case_id)
    if not pages:
        return rule_case_json, _unique(rule_warnings + ["No documents uploaded."]), "rule_based"

    client = OllamaClient()
    if not client.is_available():
        return rule_case_json, _unique(rule_warnings + ["Ollama unavailable. Using rule-based extraction."]), "rule_based"

    try:
        llm_raw = _llm_extract_case_json(client, pages)
        merged = _normalized_case_json(llm_raw, rule_case_json)
        full_text = "\n\n".join(p["text"] for p in pages if p["text"])
        warnings = _unique((merged.get("warnings") or []) + _warnings_for_case_json(merged, full_text=full_text))
        merged["warnings"] = warnings
        return merged, warnings, "ollama"
    except Exception as exc:
        return rule_case_json, _unique(rule_warnings + [f"Ollama extraction failed; fallback used: {exc}"]), "rule_based"


def save_case_extraction(
    conn,
    *,
    case_id: str,
    case_json: dict[str, Any],
    warnings: list[str],
    mode: str,
) -> dict[str, Any]:
    extraction_id = new_id("ext")
    created_at = utc_now_iso()
    conn.execute(
        """
        INSERT INTO case_extractions (extraction_id, case_id, case_json, warnings, created_at, mode)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            extraction_id,
            case_id,
            dump_json(case_json),
            dump_json(warnings),
            created_at,
            mode,
        ),
    )
    return {
        "extraction_id": extraction_id,
        "case_id": case_id,
        "case_json": case_json,
        "warnings": warnings,
        "created_at": created_at,
        "mode": mode,
    }


def latest_case_extraction(conn, case_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT extraction_id, case_id, case_json, warnings, created_at, mode
        FROM case_extractions
        WHERE case_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if not row:
        return None

    return {
        "extraction_id": row["extraction_id"],
        "case_id": row["case_id"],
        "case_json": parse_json(row["case_json"], {}),
        "warnings": parse_json(row["warnings"], []),
        "created_at": row["created_at"],
        "mode": row["mode"] if "mode" in row.keys() else "rule_based",
    }
