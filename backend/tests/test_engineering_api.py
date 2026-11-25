"""HTTP contract tests for the opt-in engineering evidence endpoint."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from fastapi.testclient import TestClient

from app.main import app
from app.engineering_grounding import INSUFFICIENT_EVIDENCE
from app.local_ai import LocalAIError


client = TestClient(app)


def _request(question="What happens in the regenerator?", topic="regenerator"):
    return client.post(
        "/api/v1/ai/engineering/ask",
        json={"question": question, "topic": topic},
    )


def test_empty_default_registry_does_not_invoke_model():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "knowledge.json"
        path.write_text('{"schema_version":1,"entries":[]}', encoding="utf-8")
        with patch("app.engineering_grounding.REGISTRY", path), \
             patch("app.engineering_api.LocalAIClient") as model:
            response = _request()
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "insufficient_evidence"
        assert payload["answer"] == INSUFFICIENT_EVIDENCE
        assert payload["sources"] == []
        assert payload["model_invoked"] is False
        assert payload["read_only"] is True
        assert payload["engineer_review_required"] is True
        model.return_value.generate.assert_not_called()


def test_missing_question_rejected():
    response = client.post("/api/v1/ai/engineering/ask", json={"topic": "regenerator"})
    assert response.status_code == 422


def test_blank_topic_rejected():
    assert _request(topic="").status_code == 422


def test_invalid_registry_returns_503_without_model_call():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "knowledge.json"
        path.write_text('{"schema_version":2,"entries":[]}', encoding="utf-8")
        with patch("app.engineering_grounding.REGISTRY", path), \
             patch("app.engineering_api.LocalAIClient") as model:
            response = _request()
        assert response.status_code == 503
        model.return_value.generate.assert_not_called()


def test_approved_evidence_calls_model_and_returns_source():
    record = {
        "id": "E-001", "status": "approved", "topic": "regenerator",
        "statement": "Synthetic text for HTTP tests only",
        "source_title": "Synthetic document", "source_locator": "sec 1",
        "reviewed_by": "Test engineer", "reviewed_at": "2026-11-25",
    }

    async def fake_generate(_self, prompt, context=None, **kwargs):
        assert context["source_ids"] == ["E-001"]
        assert kwargs["temperature"] == 0.0
        return type("Response", (), {"text": "Test-only observation [E-001]"})()

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "knowledge.json"
        path.write_text(json.dumps({"schema_version": 1, "entries": [record]}), encoding="utf-8")
        with patch("app.engineering_grounding.REGISTRY", path), \
             patch("app.engineering_api.LocalAIClient.generate", fake_generate):
            response = _request()
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "citation_screen_pass"
    assert result["sources"][0]["evidence_id"] == "E-001"
    assert result["engineer_review_required"] is True
    assert result["validation"] == "citation_presence_only_not_factuality_validation"


def test_uncited_model_response_is_not_approved():
    record = {
        "id": "E-001", "status": "approved", "topic": "regenerator",
        "statement": "Synthetic text for HTTP tests only",
        "source_title": "Synthetic document", "source_locator": "sec 1",
        "reviewed_by": "Test engineer", "reviewed_at": "2026-11-25",
    }

    async def fake_generate(_self, prompt, context=None, **kwargs):
        return type("Response", (), {"text": "Unsupported model statement"})()

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "knowledge.json"
        path.write_text(json.dumps({"schema_version": 1, "entries": [record]}), encoding="utf-8")
        with patch("app.engineering_grounding.REGISTRY", path), \
             patch("app.engineering_api.LocalAIClient.generate", fake_generate):
            response = _request()
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_evidence"
    assert response.json()["sources"] == []


def test_local_ai_error_is_sanitized():
    async def fail(*args, **kwargs):
        raise LocalAIError("Sensitive internal diagnostic")

    with patch("app.engineering_api.generate_grounded", fail):
        response = _request()
    assert response.status_code == 502
    assert "Sensitive internal diagnostic" not in response.text
