from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .utils import new_id


SUPPORTED_EXTS = {".pdf", ".txt", ".docx", ".png", ".jpg", ".jpeg", ".tiff"}


def _extract_pdf_pages(path: Path) -> tuple[list[dict[str, Any]], str]:
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append(
            {
                "page_number": i,
                "text": text,
                "confidence": 1.0 if text else 0.0,
                "extraction_method": "pdf_text",
            }
        )

    if any(p["text"] for p in pages):
        return pages, "pdf_text"

    # OCR fallback if text extraction returns empty pages
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        return pages, "pdf_text_empty"

    ocr_pages: list[dict[str, Any]] = []
    for i in range(1, len(reader.pages) + 1):
        # We cannot reliably render PDF to image without extra deps; keep placeholder page.
        ocr_pages.append(
            {
                "page_number": i,
                "text": "",
                "confidence": 0.0,
                "extraction_method": "pdf_ocr_unavailable_renderer",
            }
        )

    return ocr_pages, "pdf_ocr_unavailable_renderer"


def _extract_txt(path: Path) -> tuple[list[dict[str, Any]], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [
        {
            "page_number": 1,
            "text": text.strip(),
            "confidence": 1.0,
            "extraction_method": "txt_plain",
        }
    ], "txt_plain"


def _extract_docx(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        from docx import Document
    except Exception as exc:
        raise RuntimeError("DOCX support requires python-docx") from exc

    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
    return [
        {
            "page_number": 1,
            "text": text.strip(),
            "confidence": 1.0 if text.strip() else 0.0,
            "extraction_method": "docx_native",
        }
    ], "docx_native"


def _extract_image(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        from PIL import Image
        import pytesseract
    except Exception as exc:
        raise RuntimeError("Image OCR requires Pillow + pytesseract") from exc

    img = Image.open(path)
    text = pytesseract.image_to_string(img).strip()
    return [
        {
            "page_number": 1,
            "text": text,
            "confidence": 0.75 if text else 0.0,
            "extraction_method": "image_ocr",
        }
    ], "image_ocr"


def extract_pages(path: Path) -> tuple[list[dict[str, Any]], str]:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported extension: {ext}")

    if ext == ".pdf":
        return _extract_pdf_pages(path)
    if ext == ".txt":
        return _extract_txt(path)
    if ext == ".docx":
        return _extract_docx(path)
    return _extract_image(path)


def _chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            split = text.rfind("\n", start + int(max_chars * 0.55), end)
            if split == -1:
                split = text.rfind(" ", start + int(max_chars * 0.55), end)
            if split != -1 and split > start:
                end = split

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start = max(end - overlap, start + 1)

    return chunks


def build_chunks(pages: list[dict[str, Any]], *, max_chars: int = 900, overlap: int = 120) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in pages:
        page_num = page.get("page_number")
        text = page.get("text") or ""
        for part in _chunk_text(text, max_chars=max_chars, overlap=overlap):
            rows.append(
                {
                    "chunk_id": new_id("chk"),
                    "page_number": page_num,
                    "text": part,
                }
            )
    return rows


def process_document(conn, *, case_id: str, document_id: str, storage_path: str) -> dict[str, Any]:
    path = Path(storage_path)
    pages, extraction_method = extract_pages(path)
    chunks = build_chunks(pages)

    conn.execute("DELETE FROM doc_pages WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    for page in pages:
        conn.execute(
            """
            INSERT INTO doc_pages (document_id, page_number, text, confidence, extraction_method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                int(page.get("page_number") or 1),
                str(page.get("text") or ""),
                page.get("confidence"),
                str(page.get("extraction_method") or extraction_method),
            ),
        )

    for chunk in chunks:
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, case_id, document_id, page_number, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chunk["chunk_id"],
                case_id,
                document_id,
                chunk.get("page_number"),
                chunk.get("text") or "",
            ),
        )

    conn.execute(
        "UPDATE documents SET processed_status = ? WHERE document_id = ?",
        ("indexed", document_id),
    )

    return {
        "pages": len(pages),
        "chunks": len(chunks),
        "extraction_method": extraction_method,
    }
