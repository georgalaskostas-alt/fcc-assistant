"""Read-only first-stage P&ID PDF intake. Text-layer extraction is not diagram understanding."""
from __future__ import annotations

import io
import re

from fastapi import APIRouter, File, HTTPException, UploadFile
from pypdf import PdfReader

router = APIRouter(prefix="/api/v1/pid", tags=["pid-intelligence"])

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PAGES = 100
TAG_PATTERN = re.compile(r"(?<![A-Z0-9])(?:[A-Z]{1,6}[- ]?){1,3}\d{2,6}[A-Z]?(?![A-Z0-9])", re.I)


def inspect_pid_pdf(content: bytes) -> dict[str, object]:
    """Extract candidate labels from a text-based PDF, without making topology claims."""
    if not content.startswith(b"%PDF-"):
        raise ValueError("File is not a PDF")
    if len(content) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds 20 MB limit")
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF is not supported")
        if len(reader.pages) > MAX_PAGES:
            raise ValueError("PDF exceeds 100 page limit")
        pages = []
        candidates: dict[str, set[int]] = {}
        for page_number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            for match in TAG_PATTERN.finditer(text):
                tag = re.sub(r"\s+", "", match.group(0)).upper()
                candidates.setdefault(tag, set()).add(page_number)
            pages.append({"page": page_number, "text_available": bool(text.strip()), "characters": len(text)})
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Could not read PDF") from exc
    return {
        "mode": "pdf-text-layer",
        "read_only": True,
        "pages": pages,
        "candidate_tags": [
            {"tag": tag, "pages": sorted(page_numbers), "status": "unverified_candidate"}
            for tag, page_numbers in sorted(candidates.items())
        ][:500],
        "candidate_count": len(candidates),
        "limitations": [
            "Candidates are pattern matches, not validated equipment or instrument tags.",
            "No piping connectivity, equipment symbols or drawing corrections are inferred.",
            "Scanned/image-only PDFs require a separate visual extraction pipeline.",
            "No document contents are stored by this endpoint.",
        ],
    }


@router.post("/inspect")
async def inspect_pid(file: UploadFile = File(...)) -> dict[str, object]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Upload a PDF file")
    payload = await file.read(MAX_PDF_BYTES + 1)
    if len(payload) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds 20 MB limit")
    try:
        return inspect_pid_pdf(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
