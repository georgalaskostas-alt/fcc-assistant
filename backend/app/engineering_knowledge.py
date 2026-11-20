"""Local, fail-closed engineering evidence registry; approval is not proof of accuracy."""
from dataclasses import dataclass
import json
from pathlib import Path

class KnowledgeValidationError(ValueError):
    pass

@dataclass(frozen=True)
class Evidence:
    id: str
    topic: str
    statement: str
    source_title: str
    source_locator: str
    reviewed_by: str
    reviewed_at: str

    def as_context(self):
        return {"evidence_id": self.id, "topic": self.topic,
                "statement": self.statement, "source_title": self.source_title,
                "source_locator": self.source_locator}

FIELDS = ("id", "topic", "statement", "source_title", "source_locator", "reviewed_by", "reviewed_at")

def load_approved_evidence(path: Path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or not isinstance(document.get("entries"), list):
        raise KnowledgeValidationError("Invalid knowledge registry")
    seen, approved = set(), []
    for entry in document["entries"]:
        if not isinstance(entry, dict):
            raise KnowledgeValidationError("Invalid entry")
        ident = entry.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise KnowledgeValidationError("Missing or duplicate evidence ID")
        seen.add(ident)
        if entry.get("status") not in ("draft", "approved", "rejected"):
            raise KnowledgeValidationError("Invalid review status")
        if entry["status"] != "approved":
            continue
        if any(not isinstance(entry.get(key), str) or not entry[key].strip() for key in FIELDS):
            raise KnowledgeValidationError("Approved evidence lacks source/reviewer metadata")
        approved.append(Evidence(**{key: entry[key] for key in FIELDS}))
    return approved

def evidence_for_topic(path: Path, topic: str):
    if not isinstance(topic, str) or not topic.strip():
        return []
    return [entry.as_context() for entry in load_approved_evidence(path)
            if entry.topic.casefold() == topic.casefold()]
