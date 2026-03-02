from __future__ import annotations

import io
import re
from pathlib import Path


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    keep = max_chars - 64
    return f"{text[:keep]}\n\n[内容已截断，原始长度 {len(text)} 字符]"


def _score_extracted_text(text: str) -> int:
    compact = re.sub(r"\s+", "", text or "")
    return len(compact)


def _append_page_block(chunks: list[str], idx: int, body: str, total: int, limit: int) -> tuple[int, bool]:
    normalized = (body or "").strip()
    if not normalized:
        return total, False
    block = f"\n--- Page {idx} ---\n{normalized}\n"
    chunks.append(block)
    total += len(block)
    return total, total >= limit


def _table_to_lines(table: list[list[object]] | None) -> list[str]:
    if not table:
        return []
    lines: list[str] = []
    for row in table:
        if not row:
            continue
        cells = [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
        if not any(cells):
            continue
        lines.append(" | ".join(cells))
    return lines


def _extract_pdf_with_pdfplumber(raw_pdf: bytes, max_chars: int) -> str:
    import pdfplumber  # lazy import

    chunks: list[str] = []
    total = 0
    limit = max(512, int(max_chars))
    with pdfplumber.open(io.BytesIO(raw_pdf)) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text(layout=True) or "").strip()
            table_lines: list[str] = []
            try:
                for table in page.extract_tables() or []:
                    table_lines.extend(_table_to_lines(table))
            except Exception:
                table_lines = []

            body_parts: list[str] = []
            if text:
                body_parts.append(text)
            if table_lines:
                body_parts.append("[Extracted tables]")
                body_parts.extend(table_lines)
            total, reached = _append_page_block(chunks, idx, "\n".join(body_parts), total, limit)
            if reached:
                break
    return truncate_text("".join(chunks).strip(), limit)


def _extract_pdf_with_pypdf(raw_pdf: bytes, max_chars: int) -> str:
    from pypdf import PdfReader  # lazy import

    reader = PdfReader(io.BytesIO(raw_pdf))
    chunks: list[str] = []
    total = 0
    limit = max(512, int(max_chars))
    for idx, page in enumerate(reader.pages, start=1):
        part = page.extract_text() or ""
        total, reached = _append_page_block(chunks, idx, part, total, limit)
        if reached:
            break
    return truncate_text("".join(chunks).strip(), limit)


def extract_pdf_text_from_bytes(raw_pdf: bytes, max_chars: int) -> str:
    limit = max(512, int(max_chars))
    candidates: list[tuple[int, str]] = []
    errors: list[str] = []

    for extractor in (_extract_pdf_with_pdfplumber, _extract_pdf_with_pypdf):
        try:
            text = extractor(raw_pdf, limit)
        except Exception as exc:
            errors.append(f"{extractor.__name__}: {exc}")
            continue
        if text.strip():
            candidates.append((_score_extracted_text(text), text))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    if errors:
        raise RuntimeError("; ".join(errors))
    return ""


def extract_pdf_text_from_path(path: Path, max_chars: int) -> str:
    return extract_pdf_text_from_bytes(path.read_bytes(), max_chars=max_chars)
