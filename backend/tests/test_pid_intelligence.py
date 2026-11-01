"""First-stage P&ID intake tests; no claims about diagram connectivity."""
import io

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.app.main import app
from backend.app.pid_intelligence import inspect_pid_pdf


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_blank_pdf_reports_missing_text_layer():
    result = inspect_pid_pdf(_pdf())
    assert result["read_only"] is True
    assert result["pages"][0]["text_available"] is False
    assert result["candidate_tags"] == []


def test_invalid_pdf_rejected():
    try:
        inspect_pid_pdf(b"not a pdf")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not a PDF" in str(exc)


def test_pdf_inspection_endpoint():
    response = TestClient(app).post(
        "/api/v1/pid/inspect",
        files={"file": ("example.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "pdf-text-layer"


def test_non_pdf_upload_rejected():
    response = TestClient(app).post(
        "/api/v1/pid/inspect",
        files={"file": ("drawing.txt", b"test", "text/plain")},
    )
    assert response.status_code == 422


def test_ocr_rejects_invalid_page_before_external_dependencies():
    response = TestClient(app).post(
        "/api/v1/pid/ocr",
        data={"page": "2"},
        files={"file": ("example.pdf", _pdf(), "application/pdf")},
    )
    assert response.status_code == 422
    assert "outside" in response.json()["detail"]


def test_ocr_rejects_non_pdf_upload():
    response = TestClient(app).post(
        "/api/v1/pid/ocr",
        data={"page": "1"},
        files={"file": ("drawing.txt", b"test", "text/plain")},
    )
    assert response.status_code == 422


def test_ocr_response_has_matching_raster_and_normalized_coordinates(monkeypatch):
    """Coordinates must correspond to the exact image shown in the UI."""
    import base64
    import subprocess
    from backend.app import pid_intelligence

    monkeypatch.setattr(pid_intelligence.shutil, "which", lambda name: "/usr/local/bin/tesseract")
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t20\t30\t50\t15\t93\tPT-1234\n"
    )
    monkeypatch.setattr(
        pid_intelligence.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, tsv, ""),
    )
    result = pid_intelligence.ocr_pid_page(_pdf())
    assert base64.b64decode(result["preview_png_base64"]).startswith(bytes([137, 80, 78, 71]))
    assert result["candidates"][0]["tag"] == "PT-1234"
    assert 0 <= result["candidates"][0]["box"]["x"] <= 1
    assert 0 <= result["candidates"][0]["box"]["y"] <= 1
    assert result["read_only"] is True


def test_png_image_can_be_inspected_as_one_page():
    import fitz
    from backend.app.pid_intelligence import normalize_drawing
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 24, 24), False)
    image = pixmap.tobytes("png")
    converted = normalize_drawing(image, "drawing.png")
    assert converted.startswith(b"%PDF-")
    response = TestClient(app).post(
        "/api/v1/pid/inspect",
        files={"file": ("drawing.png", image, "image/png")},
    )
    assert response.status_code == 200
    assert len(response.json()["pages"]) == 1


def test_fake_image_is_rejected():
    response = TestClient(app).post(
        "/api/v1/pid/inspect",
        files={"file": ("drawing.jpg", b"not a jpeg", "image/jpeg")},
    )
    assert response.status_code == 422
