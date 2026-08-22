"""Parse uploaded documents into SourceDocument for indexing."""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path

from .chunking import SourceDocument

# LlamaIndex SimpleDirectoryReader handles pdf/md/txt when pypdf is installed.
READER_SUFFIXES = frozenset({".pdf", ".md", ".markdown", ".txt"})

SUPPORTED_SUFFIXES = frozenset(
    {
        ".pdf",
        ".md",
        ".markdown",
        ".txt",
        ".html",
        ".htm",
        ".json",
        ".jsonl",
        ".csv",
        ".tsv",
        ".xml",
        ".yaml",
        ".yml",
        ".rst",
        ".log",
    }
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
USER_DOCUMENT_PREFIX = "user-"


def suffix_of(filename: str | None) -> str:
    return Path(filename or "upload").suffix.casefold()


def is_supported(filename: str | None) -> bool:
    return suffix_of(filename) in SUPPORTED_SUFFIXES


def resolve_document_scope(
    *,
    document_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[str] | None:
    combined = list(document_ids or [])
    if document_id:
        combined.append(document_id)
    unique = sorted({item for item in combined if item})
    return unique or None


def is_user_document(document_id: str) -> bool:
    return document_id.startswith(USER_DOCUMENT_PREFIX)


def parse_file(path: Path, *, document_id: str, title: str | None = None) -> SourceDocument:
    suffix = path.suffix.casefold()
    display = title or path.name
    if suffix in READER_SUFFIXES:
        return _parse_with_llama_index(path, document_id=document_id, title=display)
    text = _read_text_fallback(path, suffix)
    if not text.strip():
        raise ValueError("document produced no extractable text; OCR may be required")
    return SourceDocument(
        document_id=document_id,
        text=text,
        title=display,
        source_uri=str(path),
    )


def _parse_with_llama_index(path: Path, *, document_id: str, title: str) -> SourceDocument:
    from llama_index.core import SimpleDirectoryReader

    loaded = SimpleDirectoryReader(input_files=[str(path)]).load_data()
    parts: list[str] = []
    page: int | None = None
    for item in loaded:
        piece = item.text.strip()
        if piece:
            parts.append(piece)
        metadata = dict(item.metadata)
        page_value = metadata.get("page_label") or metadata.get("page_number")
        try:
            page = int(page_value) if page_value is not None else page
        except (TypeError, ValueError):
            pass
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("document produced no extractable text; OCR may be required")
    return SourceDocument(
        document_id=document_id,
        text=text,
        title=title,
        source_uri=str(path),
        page=page,
        metadata={"file_name": path.name},
    )


def _read_text_fallback(path: Path, suffix: str) -> str:
    raw = path.read_bytes()
    if suffix == ".json":
        return _json_to_text(json.loads(raw.decode("utf-8", errors="replace")))
    if suffix == ".jsonl":
        lines: list[str] = []
        for line in raw.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(_json_to_text(json.loads(line)))
            except json.JSONDecodeError:
                lines.append(line)
        return "\n".join(lines)
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        reader = csv.reader(io.StringIO(raw.decode("utf-8", errors="replace")), delimiter=delimiter)
        return "\n".join(" | ".join(row) for row in reader if any(cell.strip() for cell in row))
    if suffix in {".html", ".htm"}:
        return _strip_html(raw.decode("utf-8", errors="replace"))
    return raw.decode("utf-8", errors="replace")


def _json_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(f"{key}: {_json_to_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_json_to_text(item) for item in value)
    return str(value)


def _strip_html(text: str) -> str:
    import re

    without_scripts = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
    return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()
