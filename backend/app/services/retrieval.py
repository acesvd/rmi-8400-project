from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text or "")]


def _score(query_tokens: list[str], text_tokens: list[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0
    q = Counter(query_tokens)
    t = Counter(text_tokens)

    numerator = 0.0
    q_norm = 0.0
    t_norm = 0.0
    for tok, qv in q.items():
        tv = t.get(tok, 0)
        numerator += qv * tv
        q_norm += qv * qv
    for tv in t.values():
        t_norm += tv * tv

    if q_norm == 0 or t_norm == 0:
        return 0.0
    return numerator / (math.sqrt(q_norm) * math.sqrt(t_norm))


def retrieve_case_chunks(conn, *, case_id: str, query: str, top_k: int = 8) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.document_id, c.page_number, c.text, d.filename
        FROM chunks c
        JOIN documents d ON d.document_id = c.document_id
        WHERE c.case_id = ?
        """,
        (case_id,),
    ).fetchall()

    q_tokens = _tokenize(query)
    scored: list[dict[str, Any]] = []
    for row in rows:
        text = row["text"] or ""
        score = _score(q_tokens, _tokenize(text))
        if score <= 0:
            continue
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "file_name": row["filename"],
                "page_number": row["page_number"],
                "text": text,
                "score": round(score, 4),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
