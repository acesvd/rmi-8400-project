from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from ..config import ARTIFACT_DIR
from .case_extraction import latest_case_extraction
from .utils import dump_json, new_id, parse_json, utc_now_iso


def _next_version(conn, *, case_id: str, artifact_type: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM artifacts WHERE case_id = ? AND type = ?",
        (case_id, artifact_type),
    ).fetchone()
    return int(row["v"] or 0) + 1


def _wrap_line_for_pdf(line: str, width_chars: int = 95) -> list[str]:
    clean = line.rstrip()
    if not clean:
        return [""]
    return textwrap.wrap(
        clean,
        width=width_chars,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [clean]


def _normalize_markdown_for_pdf(text: str) -> list[str]:
    out: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue

        # Skip markdown-only separator lines.
        if re.fullmatch(r"[-=*#\s]{3,}", line):
            continue

        # Demote headings and preserve a blank line before major sections.
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)

        # Normalize bullets/numbered list into simple bullets.
        line = re.sub(r"^\s*\d+\.\s+", "- ", line)
        line = re.sub(r"^\s*[*+-]\s+", "- ", line)

        # Remove common markdown emphasis markers.
        line = line.replace("**", "").replace("__", "").replace("`", "")
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", line)
        line = re.sub(r"\s{2,}", " ", line).strip()

        if line:
            out.append(line)

    if not out:
        return ["No letter content was available."]
    return out


def _write_text_pdf(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=LETTER)
    width, height = LETTER
    left_margin = 50
    top_margin = 50
    bottom_margin = 50
    line_height = 14

    c.setFont("Helvetica", 11)
    y = height - top_margin
    for line in lines:
        wrapped_lines = _wrap_line_for_pdf(line)
        for chunk in wrapped_lines:
            if y < bottom_margin:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = height - top_margin
            c.drawString(left_margin, y, chunk)
            y -= line_height
    c.save()


def _latest_letter(conn, case_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT artifact_id, version, storage_path, metadata, created_at
        FROM artifacts
        WHERE case_id = ? AND type = 'letter'
        ORDER BY version DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "artifact_id": row["artifact_id"],
        "version": row["version"],
        "storage_path": row["storage_path"],
        "metadata": parse_json(row["metadata"], {}),
        "created_at": row["created_at"],
    }


def generate_packet_artifact(conn, *, case_id: str, include_uploaded_pdfs: bool = True) -> dict[str, Any]:
    case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case_row:
        raise ValueError("Case not found")

    letter = _latest_letter(conn, case_id)
    if not letter:
        raise ValueError("No letter artifact found. Run /cases/{case_id}/letter first.")

    extraction = latest_case_extraction(conn, case_id) or {"case_json": {}}
    case_json = extraction.get("case_json") or {}
    ids = case_json.get("identifiers") or {}

    docs = conn.execute(
        "SELECT document_id, filename, storage_path, type FROM documents WHERE case_id = ? ORDER BY uploaded_at",
        (case_id,),
    ).fetchall()

    version = _next_version(conn, case_id=case_id, artifact_type="packet_pdf")
    artifact_id = new_id("art")
    created_at = utc_now_iso()

    case_dir = ARTIFACT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    cover_pdf = case_dir / f"packet_cover_v{version}.pdf"
    letter_pdf = case_dir / f"packet_letter_v{version}.pdf"
    packet_pdf = case_dir / f"packet_v{version}.pdf"

    cover_lines = [
        "Appeals Packet Cover Sheet",
        "",
        f"Case ID: {case_id}",
        f"Title: {case_row['title']}",
        f"Claim #: {ids.get('claim_number', 'unknown')}",
        f"Auth #: {ids.get('auth_number', 'unknown')}",
        "",
        "Attachments:",
    ]
    for idx, d in enumerate(docs, start=1):
        cover_lines.append(f"{idx}. {d['filename']} ({d['type']})")
    _write_text_pdf(cover_pdf, cover_lines)

    letter_text = Path(letter["storage_path"]).read_text(encoding="utf-8")
    _write_text_pdf(letter_pdf, _normalize_markdown_for_pdf(letter_text))

    writer = PdfWriter()

    for source in [cover_pdf, letter_pdf]:
        reader = PdfReader(str(source))
        for p in reader.pages:
            writer.add_page(p)

    merged_docs: list[str] = []
    if include_uploaded_pdfs:
        for d in docs:
            path = Path(d["storage_path"])
            if path.suffix.lower() != ".pdf" or not path.exists():
                continue
            try:
                reader = PdfReader(str(path))
                for p in reader.pages:
                    writer.add_page(p)
                merged_docs.append(d["filename"])
            except Exception:
                continue

    with packet_pdf.open("wb") as f:
        writer.write(f)

    metadata = {
        "letter_artifact_id": letter["artifact_id"],
        "merged_source_pdfs": merged_docs,
    }

    conn.execute(
        """
        INSERT INTO artifacts (artifact_id, case_id, type, version, storage_path, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            case_id,
            "packet_pdf",
            version,
            str(packet_pdf),
            dump_json(metadata),
            created_at,
        ),
    )

    return {
        "artifact_id": artifact_id,
        "case_id": case_id,
        "type": "packet_pdf",
        "version": version,
        "storage_path": str(packet_pdf),
        "metadata": metadata,
        "created_at": created_at,
    }
