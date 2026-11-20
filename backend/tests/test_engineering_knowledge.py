import json
from pathlib import Path
import tempfile
import unittest
from app.engineering_knowledge import KnowledgeValidationError, evidence_for_topic, load_approved_evidence

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "knowledge.json"

    def save(self, entries):
        self.path.write_text(json.dumps({"schema_version": 1, "entries": entries}))

    def test_empty_registry(self):
        self.save([])
        self.assertEqual(evidence_for_topic(self.path, "regenerator"), [])

    def test_draft_is_not_verified(self):
        self.save([{"id": "K1", "status": "draft", "topic": "regenerator", "statement": "Unreviewed"}])
        self.assertEqual(evidence_for_topic(self.path, "regenerator"), [])

    def test_approved_requires_provenance(self):
        self.save([{"id": "K1", "status": "approved", "topic": "regenerator", "statement": "Unproven"}])
        with self.assertRaises(KnowledgeValidationError):
            load_approved_evidence(self.path)

    def test_approved_is_traceable_and_filtered(self):
        self.save([{"id": "K1", "status": "approved", "topic": "regenerator",
                    "statement": "Synthetic test text", "source_title": "Synthetic test document",
                    "source_locator": "section 1", "reviewed_by": "Test reviewer", "reviewed_at": "2026-11-18"}])
        self.assertEqual(len(evidence_for_topic(self.path, "REGENERATOR")), 1)
        self.assertEqual(evidence_for_topic(self.path, "fractionator"), [])

    def test_duplicate_ids_rejected(self):
        self.save([{"id": "K1", "status": "draft"}, {"id": "K1", "status": "rejected"}])
        with self.assertRaises(KnowledgeValidationError):
            load_approved_evidence(self.path)
