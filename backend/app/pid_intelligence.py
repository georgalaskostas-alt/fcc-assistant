"""Read-only first-stage P&ID PDF intake. Text-layer extraction is not diagram understanding."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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


def ocr_pid_page(content: bytes, page_number: int = 1) -> dict[str, object]:
    """Optional local OCR of one PDF page; results are unverified and read-only."""
    # Apply the same input restrictions as text-layer inspection.
    overview = inspect_pid_pdf(content)
    if page_number < 1 or page_number > len(overview["pages"]):
        raise ValueError("Page number is outside the PDF")
    if shutil.which("tesseract") is None:
        raise RuntimeError("Local Tesseract OCR is not installed. Install with: brew install tesseract")
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PDF rendering dependency missing. Install PyMuPDF in the backend environment.") from exc
    try:
        document = fitz.open(stream=content, filetype="pdf")
        try:
            page = document.load_page(page_number - 1)
            # Limit raster size to avoid excessive memory use on large engineering sheets.
            scale = min(2.0, 3200 / max(page.rect.width, page.rect.height))
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            with tempfile.TemporaryDirectory(prefix="fcc-pid-ocr-") as temp_dir:
                image_path = Path(temp_dir) / "page.png"
                pixmap.save(str(image_path))
                completed = subprocess.run(
                    ["tesseract", str(image_path), "stdout", "-l", "eng", "--psm", "11", "tsv"],
                    capture_output=True, text=True, timeout=90, check=False,
                )
            if completed.returncode:
                raise RuntimeError("Local OCR process failed")
            rows = completed.stdout.splitlines()
            if not rows:
                return {"page": page_number, "engine": "tesseract-local", "candidates": [], "read_only": True}
            import csv
            candidates = []
            seen = set()
            for row in csv.DictReader(rows, delimiter="\t"):
                if row.get("level") != "5":
                    continue
                raw = (row.get("text") or "").strip()
                if not TAG_PATTERN.fullmatch(raw):
                    continue
                tag = re.sub(r"\s+", "", raw).upper()
                try:
                    confidence = float(row["conf"])
                    left, top = int(row["left"]), int(row["top"])
                    width, height = int(row["width"]), int(row["height"])
                except (ValueError, TypeError, KeyError):
                    continue
                if confidence < 20:
                    continue
                key = (tag, left, top)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append({
                    "tag": tag, "confidence": confidence,
                    "box": {"x": left / pixmap.width, "y": top / pixmap.height,
                            "width": width / pixmap.width, "height": height / pixmap.height},
                    "status": "unverified_ocr_candidate",
                })
            return {
                "page": page_number, "engine": "tesseract-local",
                "candidates": candidates[:500], "read_only": True,
                "warning": "OCR labels and coordinates are unverified. No diagram topology is inferred.",
            }
        finally:
            document.close()
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Local OCR timed out") from exc


@router.post("/ocr")
async def ocr_pid(file: UploadFile = File(...), page: int = Form(1)) -> dict[str, object]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Upload a PDF file")
    payload = await file.read(MAX_PDF_BYTES + 1)
    if len(payload) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds 20 MB limit")
    try:
        return ocr_pid_page(payload, page)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
