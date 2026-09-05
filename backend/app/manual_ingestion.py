from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from pypdf import PdfReader


MAX_MANUAL_BYTES = 25 * 1024 * 1024
SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md"}


class ManualIngestionError(ValueError):
    pass


@dataclass(frozen=True)
class ManualChunk:
    chunk_id: str
    text: str
    page: int | None = None


@dataclass(frozen=True)
class ManualIngestionResult:
    storage_id: str
    original_name: str
    stored_path: str
    index_path: str
    character_count: int
    chunk_count: int
    pages: int | None


def _safe_unit_key(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").casefold()
    if not normalized:
        raise ManualIngestionError("Invalid unit key")
    return normalized


def _safe_filename(value: str) -> str:
    name = Path(value).name.strip()
    if not name:
        raise ManualIngestionError("Manual filename is required")
    suffix = Path(name).suffix.casefold()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ManualIngestionError("Supported manual formats: PDF, TXT, MD")
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(name).stem).strip("-._") or "manual"
    return f"{stem}{suffix}"


def _manual_root(root: Path | None = None) -> Path:
    return root or (Path.home() / ".fcc-assistant" / "manuals")


def _chunk_text(text: str, *, page: int | None = None, max_chars: int = 1800) -> list[ManualChunk]:
    clean = re.sub(r"\r\n?", "\n", text)
    blocks = [re.sub(r"\s+", " ", block).strip() for block in re.split(r"\n\s*\n", clean) if block.strip()]
    chunks: list[ManualChunk] = []
    buffer = ""
    for block in blocks:
        if len(block) > max_chars:
            pieces = [block[index:index + max_chars] for index in range(0, len(block), max_chars)]
        else:
            pieces = [block]
        for piece in pieces:
            candidate = f"{buffer}\n\n{piece}".strip() if buffer else piece
            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(ManualChunk(chunk_id=uuid4().hex, text=buffer, page=page))
                buffer = piece
    if buffer:
        chunks.append(ManualChunk(chunk_id=uuid4().hex, text=buffer, page=page))
    return chunks


def _extract_pdf(data: bytes) -> tuple[str, list[ManualChunk], int]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises several parser-specific exceptions
        raise ManualIngestionError(f"Could not read PDF: {exc}") from exc
    all_text: list[str] = []
    chunks: list[ManualChunk] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            all_text.append(text)
            chunks.extend(_chunk_text(text, page=page_number))
    return "\n\n".join(all_text), chunks, len(reader.pages)


def _extract_text(data: bytes) -> tuple[str, list[ManualChunk], None]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1253")
        except UnicodeDecodeError as exc:
            raise ManualIngestionError("Text manual must be UTF-8 or Windows Greek text") from exc
    return text, _chunk_text(text), None


def ingest_manual(unit_key: str, filename: str, data: bytes, *, root: Path | None = None) -> ManualIngestionResult:
    if not data:
        raise ManualIngestionError("Manual file is empty")
    if len(data) > MAX_MANUAL_BYTES:
        raise ManualIngestionError("Manual exceeds the 25 MB local ingestion limit")

    safe_unit = _safe_unit_key(unit_key)
    safe_name = _safe_filename(filename)
    suffix = Path(safe_name).suffix.casefold()
    storage_id = uuid4().hex
    unit_root = _manual_root(root) / safe_unit
    files_dir = unit_root / "files"
    indexes_dir = unit_root / "indexes"
    files_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)

    stored_path = files_dir / f"{storage_id}-{safe_name}"
    stored_path.write_bytes(data)

    try:
        if suffix == ".pdf":
            text, chunks, pages = _extract_pdf(data)
        else:
            text, chunks, pages = _extract_text(data)
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    if not text.strip() or not chunks:
        stored_path.unlink(missing_ok=True)
        raise ManualIngestionError("No readable text was extracted from the manual")

    index_path = indexes_dir / f"{storage_id}.json"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "storage_id": storage_id,
        "unit_key": safe_unit,
        "original_name": safe_name,
        "stored_path": str(stored_path),
        "pages": pages,
        "character_count": len(text),
        "chunks": [asdict(chunk) for chunk in chunks],
    }
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return ManualIngestionResult(
        storage_id=storage_id,
        original_name=safe_name,
        stored_path=str(stored_path),
        index_path=str(index_path),
        character_count=len(text),
        chunk_count=len(chunks),
        pages=pages,
    )


def _query_terms(query: str) -> list[str]:
    return [term for term in re.findall(r"[\w%./-]+", query.casefold(), flags=re.UNICODE) if len(term) >= 2]


def search_manual_index(unit_key: str, query: str, *, limit: int = 8, root: Path | None = None) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []
    safe_unit = _safe_unit_key(unit_key)
    indexes_dir = _manual_root(root) / safe_unit / "indexes"
    if not indexes_dir.exists():
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for path in indexes_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        chunks = payload.get("chunks")
        if not isinstance(chunks, list):
            continue
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            text = str(chunk.get("text") or "")
            haystack = text.casefold()
            score = sum(haystack.count(term) for term in terms)
            if score <= 0:
                continue
            scored.append((score, {
                "manual_storage_id": payload.get("storage_id"),
                "manual_name": payload.get("original_name"),
                "chunk_id": chunk.get("chunk_id"),
                "page": chunk.get("page"),
                "text": text,
                "score": score,
            }))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[: max(1, min(limit, 25))]]
