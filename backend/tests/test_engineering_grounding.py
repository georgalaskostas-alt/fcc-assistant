"""Offline, deterministic tests for opt-in FCC engineering grounding."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from app.engineering_grounding import (
    INSUFFICIENT_EVIDENCE,
    approved_grounding_context,
    generate_grounded,
    validate_grounded_answer,
)


class _ModelResponse:
    def __init__(self, text):
        self.text = text


class _FakeClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    async def generate(self, question, context=None, **kwargs):
        self.calls.append((question, context, kwargs))
        return _ModelResponse(self.answer)


class EngineeringGroundingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = Path(self.tmp.name) / "evidence.json"

    def write(self, entries):
        self.registry.write_text(json.dumps({"schema_version": 1, "entries": entries}),
                                 encoding="utf-8")

    def approved(self):
        return {"id": "E-001", "status": "approved", "topic": "regenerator",
                "statement": "Synthetic evidence for testing only",
                "source_title": "Synthetic source", "source_locator": "section 1",
                "reviewed_by": "Test reviewer", "reviewed_at": "2026-11-22"}

    def test_empty_registry_refuses_without_model_call(self):
        self.write([])
        client = _FakeClient("fabricated")
        result = asyncio.run(generate_grounded(client, "Explain catalyst", "regenerator", self.registry))
        self.assertFalse(result["grounded"])
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["answer"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(client.calls, [])

    def test_draft_is_not_supplied(self):
        entry = self.approved()
        entry["status"] = "draft"
        self.write([entry])
        self.assertEqual(approved_grounding_context("regenerator", self.registry)["evidence"], [])

    def test_approved_source_passed_to_local_model(self):
        self.write([self.approved()])
        client = _FakeClient("According to the synthetic source [E-001].")
        result = asyncio.run(generate_grounded(client, "Explain example", "regenerator", self.registry))
        self.assertTrue(result["grounded"])
        self.assertEqual(result["sources"][0]["evidence_id"], "E-001")
        self.assertEqual(client.calls[0][1]["source_ids"], ["E-001"])

    def test_missing_citation_does_not_pass(self):
        self.write([self.approved()])
        result = asyncio.run(generate_grounded(_FakeClient("Unsupported technical claim"),
                                               "Explain example", "regenerator", self.registry))
        self.assertFalse(result["grounded"])

    def test_unknown_citation_does_not_pass(self):
        self.write([self.approved()])
        result = asyncio.run(generate_grounded(_FakeClient("Claim [E-999]"),
                                               "Explain example", "regenerator", self.registry))
        self.assertFalse(result["grounded"])

    def test_citation_presence_is_not_accuracy(self):
        self.assertTrue(validate_grounded_answer("Incorrect claim [E-001]", ["E-001"]))
        self.assertFalse(validate_grounded_answer("No citation", ["E-001"]))


if __name__ == "__main__":
    unittest.main()
