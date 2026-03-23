from __future__ import annotations

from typing import Any

from ..config import OLLAMA_CHAT_MODEL
from .case_extraction import latest_case_extraction
from .llm import OllamaClient
from .retrieval import retrieve_case_chunks
from .utils import dump_json


def _short(text: str, n: int = 360) -> str:
    text = " ".join((text or "").split())
    return text[:n] + ("..." if len(text) > n else "")


def _fallback_answer(question: str, extraction: dict[str, Any] | None, sources: list[dict[str, Any]]) -> str:
    reasons = ((extraction or {}).get("case_json") or {}).get("denial_reasons") or []
    warnings = ((extraction or {}).get("case_json") or {}).get("warnings") or []

    q = (question or "").lower()
    if "why" in q and "deny" in q:
        if reasons:
            reason_lines = [
                f"- {r.get('label', 'unknown').replace('_', ' ').title()}: {r.get('supporting_quote', '')}"
                for r in reasons
            ]
            return (
                "Based on your uploaded documents, likely denial basis:\n"
                + "\n".join(reason_lines)
                + "\n\nI can provide a better explanation once Ollama is running."
            )
        return "I could not confidently find a denial reason in your uploaded text."

    if "simple" in q or "explain" in q:
        if reasons:
            labels = ", ".join(r.get("label", "unknown") for r in reasons)
            return (
                f"Simple explanation: your claim appears tied to {labels}. "
                "This usually means the insurer wants additional proof or policy alignment."
            )

    if sources:
        first = sources[0]
        return (
            "I used your case documents to find this relevant excerpt:\n"
            f"{_short(first.get('text', ''))}\n"
            "For richer explanations, start Ollama and ask again."
        )

    if warnings:
        return "I need more document evidence before answering confidently. " + " ".join(warnings)

    return "I need more case context to answer this. Upload denial/EOB docs and run extraction first."


def answer_case_question(conn, *, case_id: str, question: str) -> dict[str, Any]:
    extraction = latest_case_extraction(conn, case_id)
    sources = retrieve_case_chunks(conn, case_id=case_id, query=question, top_k=8)

    citations = [
        {
            "chunk_id": s.get("chunk_id"),
            "document_id": s.get("document_id"),
            "file_name": s.get("file_name"),
            "page_number": s.get("page_number"),
            "snippet": _short(s.get("text", ""), 300),
            "score": s.get("score"),
        }
        for s in sources
    ]

    client = OllamaClient()
    if client.is_available():
        try:
            system_prompt = (
                "You are a claims appeal assistant for patients. "
                "Answer clearly and safely. Use this format:\n"
                "1) What your uploaded documents indicate\n"
                "2) Simple explanation\n"
                "3) General insurance/medical context (clearly labeled as general info)\n"
                "4) Next step\n"
                "Never invent case facts. If missing, say not found. "
                "Keep citations inline like '(file_name p.X)'. "
                "Include disclaimer: informational support only, not legal or medical advice."
            )
            user_prompt = (
                f"Question: {question}\n\n"
                f"Case extraction: {dump_json((extraction or {}).get('case_json') or {})}\n\n"
                f"Retrieved evidence: {dump_json(citations)}"
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
                "sources": citations,
                "mode": "ollama",
            }
        except Exception as exc:
            return {
                "answer": _fallback_answer(question, extraction, sources),
                "sources": citations,
                "mode": "fallback",
                "warning": f"Ollama chat failed: {exc}",
            }

    return {
        "answer": _fallback_answer(question, extraction, sources),
        "sources": citations,
        "mode": "fallback",
        "warning": "Ollama unavailable",
    }
