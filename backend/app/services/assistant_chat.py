"""Case Q&A assistant with appealability data as available context.

The LLM receives the user's question, document evidence, and appealability data
(overturn rates, precedent cases, insurer benchmarks) as context. It decides
how to use this data based on the question — not a rigid template.

The fallback (when Ollama is unavailable) gives a brief direct answer only for
questions it can handle with the structured data, and defers to "start Ollama"
for open-ended questions.
"""

from __future__ import annotations

from typing import Any

from ..config import OLLAMA_CHAT_MODEL
from .case_extraction import latest_case_extraction
from .denial_outcomes import get_appealability
from .llm import OllamaClient
from .retrieval import retrieve_case_chunks
from .utils import dump_json


def _short(text: str, n: int = 800) -> str:
    text = " ".join((text or "").split())
    return text[:n] + ("..." if len(text) > n else "")


# ---------------------------------------------------------------------------
# Build context blocks — these are DATA the LLM can use, not answer templates
# ---------------------------------------------------------------------------

def _build_appealability_context(appealability: dict[str, Any] | None) -> str:
    """Format appealability data as context for the LLM. NOT an answer template."""
    if not appealability:
        return ""

    parts = []
    classification = appealability.get("denial_classification", "unknown")
    parts.append(f"[DENIAL CLASSIFICATION: {classification}]")

    if classification == "R1":
        a_score = appealability.get("a_score") or {}
        if a_score.get("overturn_rate") is not None:
            rate_pct = int(a_score["overturn_rate"] * 100)
            parts.append(
                f"[OVERTURN DATA: {rate_pct}% overturn rate, "
                f"{a_score.get('sample_size', 0)} cases, "
                f"confidence: {a_score.get('confidence', 'unknown')}, "
                f"years: {a_score.get('year_range', 'N/A')}]"
            )
        precedent = appealability.get("precedent_cases") or []
        if precedent:
            parts.append("[PRECEDENT CASES — similar overturned IMR decisions:]")
            for pc in precedent[:3]:
                desc = _short(pc.get("description", ""), 200)
                parts.append(
                    f"  Case {pc.get('reference_id', '')} ({pc.get('year', '')}) | "
                    f"{pc.get('diagnosis', '')} | {pc.get('treatment', '')} | "
                    f"Relevance: {pc.get('relevance_score', 0):.2f} | "
                    f"Finding: {desc}"
                )

    elif classification == "R2":
        benchmark = appealability.get("insurer_benchmark") or {}
        if benchmark.get("internal_overturn_pct") is not None:
            parts.append(
                f"[INSURER BENCHMARK: {benchmark.get('insurer', 'unknown')} — "
                f"internal appeal overturn: {benchmark['internal_overturn_pct']}%"
                + (f", external review: {benchmark['external_overturn_pct']}%"
                   if benchmark.get("external_overturn_pct") is not None else "")
                + f" (year: {benchmark.get('year', 'N/A')})]"
            )

    recs = appealability.get("recommendations") or []
    non_precedent = [r for r in recs if not r.startswith("Precedent case ")]
    if non_precedent:
        parts.append("[RECOMMENDATIONS: " + " | ".join(non_precedent[:2]) + "]")

    return "\n".join(parts)


def _build_precedent_sources(appealability: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Convert IMR precedent cases into source citations for the Sources panel.

    Full Findings text is included — the frontend can truncate with an
    expand/"..." button.
    """
    if not appealability or appealability.get("denial_classification") != "R1":
        return []

    sources = []
    for pc in (appealability.get("precedent_cases") or [])[:3]:
        desc = pc.get("description", "")
        if not desc:
            continue
        sources.append({
            "chunk_id": f"imr_{pc.get('reference_id', '')}",
            "document_id": "S1_IMR_CSV",
            "file_name": f"IMR Case {pc.get('reference_id', '')}",
            "page_number": None,
            "snippet": desc,  # full text for frontend expand
            "score": pc.get("relevance_score"),
            "imr_reference": pc.get("reference_id", ""),
            "imr_year": pc.get("year", ""),
            "imr_diagnosis": pc.get("diagnosis", ""),
            "imr_treatment": pc.get("treatment", ""),
            "imr_determination": pc.get("determination", ""),
        })
    return sources


# ---------------------------------------------------------------------------
# Fallback — minimal, only for when Ollama is down
# ---------------------------------------------------------------------------

def _fallback_answer(
    question: str,
    extraction: dict[str, Any] | None,
    sources: list[dict[str, Any]],
    appealability: dict[str, Any] | None = None,
) -> str:
    """Simple keyword-based fallback when Ollama is unavailable.

    Keeps answers brief and factual. Does NOT impose a rigid structure —
    just returns the most relevant data for the question.
    """
    reasons = ((extraction or {}).get("case_json") or {}).get("denial_reasons") or []
    q = (question or "").lower()

    # If we have appealability data and the question seems appeal-related
    if appealability and any(kw in q for kw in (
        "chance", "likelihood", "odds", "success", "win", "overturn",
        "should i appeal", "worth", "probability", "how likely",
    )):
        a_score = appealability.get("a_score") or {}
        if a_score.get("overturn_rate") is not None:
            rate_pct = int(a_score["overturn_rate"] * 100)
            return (
                f"Based on {a_score.get('sample_size', 0):,} similar IMR cases, "
                f"{rate_pct}% were overturned. See Sources below for similar precedent cases. "
                f"Start Ollama for a detailed analysis of your specific situation."
            )

    # Why denied
    if "why" in q and ("deni" in q or "deny" in q):
        if reasons:
            lines = [f"- {r.get('label', '').replace('_', ' ').title()}: "
                     f"{r.get('supporting_quote', '')}" for r in reasons]
            return "Denial basis:\n" + "\n".join(lines)

    # General — use document chunks if available
    if sources:
        return (
            "From your documents:\n"
            + _short(sources[0].get("text", sources[0].get("snippet", "")), 400)
            + "\n\nStart Ollama for a full analysis."
        )

    return "Upload your denial letter and run extraction so I can help."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def answer_case_question(conn, *, case_id: str, question: str) -> dict[str, Any]:
    extraction = latest_case_extraction(conn, case_id)
    sources = retrieve_case_chunks(conn, case_id=case_id, query=question, top_k=8)

    # Compute appealability from case extraction
    case_json = (extraction or {}).get("case_json") or {}

    # If extraction didn't find denial reasons, infer from raw chunk text
    if not case_json.get("denial_reasons") and sources:
        chunk_text = " ".join(s.get("text", "") for s in sources).lower()
        inferred_reasons = []
        if "not medically necessary" in chunk_text or "medical necessity" in chunk_text:
            inferred_reasons.append({"label": "medical_necessity", "keyword": "medical necessity",
                                      "supporting_quote": "(inferred from document text)"})
        elif "experimental" in chunk_text or "investigational" in chunk_text:
            inferred_reasons.append({"label": "medical_necessity", "keyword": "experimental",
                                      "supporting_quote": "(inferred from document text)"})
        elif "prior authorization" in chunk_text or "pre-authorization" in chunk_text:
            inferred_reasons.append({"label": "prior_authorization", "keyword": "prior authorization",
                                      "supporting_quote": "(inferred from document text)"})
        elif "out-of-network" in chunk_text or "out of network" in chunk_text:
            inferred_reasons.append({"label": "out_of_network", "keyword": "out of network",
                                      "supporting_quote": "(inferred from document text)"})
        if inferred_reasons:
            case_json = dict(case_json)
            case_json["denial_reasons"] = inferred_reasons

    try:
        appealability = get_appealability(case_json) if case_json.get("denial_reasons") else None
    except Exception:
        appealability = None

    # Build citations: document chunks + IMR precedent cases
    doc_citations = [
        {
            "chunk_id": s.get("chunk_id"),
            "document_id": s.get("document_id"),
            "file_name": s.get("file_name"),
            "page_number": s.get("page_number"),
            "snippet": s.get("text", ""),  # full text, no truncation
            "score": s.get("score"),
        }
        for s in sources
    ]
    imr_citations = _build_precedent_sources(appealability)
    all_citations = doc_citations + imr_citations

    # --- LLM path: let the model interpret the question freely ---
    client = OllamaClient()
    if client.is_available():
        try:
            appeal_context = _build_appealability_context(appealability)

            # Compact case summary — not the full dump
            payer = case_json.get("payer", "unknown")
            denial_labels = ", ".join(
                r.get("label", "").replace("_", " ") for r in case_json.get("denial_reasons", [])
            ) or "not identified"
            patient = (case_json.get("parties") or {}).get("patient_name", "unknown")

            # Top 2 document excerpts for grounding
            excerpts = ""
            for i, c in enumerate(doc_citations[:2], 1):
                text = (c.get("snippet") or "")[:300]
                fname = c.get("file_name", "document")
                page = c.get("page_number", "?")
                excerpts += f"[Doc {i}: {fname} p.{page}] {text}\n"

            system_prompt = (
                "You are a claims appeal assistant helping a patient understand their "
                "insurance denial and appeal options.\n\n"
                "You have access to:\n"
                "- The patient's denial letter excerpts\n"
                "- Historical appeal overturn data from the CA DMHC IMR database\n"
                "- Similar precedent cases that were overturned at independent review\n"
                "- Insurer-specific appeal benchmarks\n\n"
                "Answer the patient's question naturally and helpfully. "
                "Use the data provided when relevant — cite IMR case IDs and statistics "
                "when discussing appeal chances. If the question is about something else "
                "(deadlines, process, next steps, etc.), answer that instead.\n\n"
                "Keep answers under 250 words. Be direct. "
                "When citing precedent, briefly explain why the case is relevant. "
                "End with: *Informational only, not legal/medical advice.*"
            )

            user_prompt = (
                f"Patient: {patient} | Payer: {payer} | Denial: {denial_labels}\n\n"
                f"Document excerpts:\n{excerpts}\n"
                f"Appeal data:\n{appeal_context}\n\n"
                f"Question: {question}"
            )

            answer = client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model=OLLAMA_CHAT_MODEL,
                temperature=0.2,
            )
            if not answer.strip():
                raise RuntimeError("Empty LLM answer")
            return {
                "answer": answer,
                "sources": all_citations,
                "mode": "ollama",
            }
        except Exception as exc:
            return {
                "answer": _fallback_answer(question, extraction, sources, appealability),
                "sources": all_citations,
                "mode": "fallback",
                "warning": f"Ollama chat failed: {exc}",
            }

    return {
        "answer": _fallback_answer(question, extraction, sources, appealability),
        "sources": all_citations,
        "mode": "fallback",
        "warning": "Ollama unavailable",
    }