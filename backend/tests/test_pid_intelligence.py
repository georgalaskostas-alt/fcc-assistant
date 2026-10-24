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
