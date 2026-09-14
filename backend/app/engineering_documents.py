"""Controlled engineering-document change workflow.

The assistant may prepare proposed changes and redlines, but this module never
modifies or replaces an approved engineering master automatically. Promotion to
an approved revision requires an explicit human approval event.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class ChangeStatus(StrEnum):
    PROPOSED = "proposed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DocumentReference:
    document_id: str
    title: str
    revision: str
    document_type: str
    source_path: str | None = None
    unit_key: str | None = None
    equipment_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class RedlineInstruction:
    description: str
    page: int | None = None
    target_reference: str | None = None
    markup_kind: str = "note"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalEvent:
    actor_id: str
    action: str
    timestamp: str
    comment: str = ""


@dataclass
class ProposedDocumentChange:
    id: str
    document: DocumentReference
    requested_by: str
    reason: str
    instructions: list[RedlineInstruction]
    status: ChangeStatus = ChangeStatus.PROPOSED
    created_at: str = ""
    events: list[ApprovalEvent] = field(default_factory=list)
    proposed_revision: str | None = None
    generated_artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class DocumentChangeError(ValueError):
    pass


class EngineeringDocumentWorkflow:
    """Durable, non-destructive workflow for AI-assisted document corrections."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".fcc-assistant" / "engineering-document-changes.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise DocumentChangeError("Engineering document workflow store is invalid")
        return raw

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> ProposedDocumentChange:
        document_raw = raw.get("document") or {}
        instructions_raw = raw.get("instructions") or []
        events_raw = raw.get("events") or []
        return ProposedDocumentChange(
            id=str(raw["id"]),
            document=DocumentReference(
                document_id=str(document_raw["document_id"]),
                title=str(document_raw.get("title") or document_raw["document_id"]),
                revision=str(document_raw.get("revision") or ""),
                document_type=str(document_raw.get("document_type") or "unknown"),
                source_path=document_raw.get("source_path"),
                unit_key=document_raw.get("unit_key"),
                equipment_keys=tuple(document_raw.get("equipment_keys") or ()),
            ),
            requested_by=str(raw.get("requested_by") or "unknown"),
            reason=str(raw.get("reason") or ""),
            instructions=[RedlineInstruction(**item) for item in instructions_raw],
            status=ChangeStatus(str(raw.get("status") or ChangeStatus.PROPOSED.value)),
            created_at=str(raw.get("created_at") or ""),
            events=[ApprovalEvent(**item) for item in events_raw],
            proposed_revision=raw.get("proposed_revision"),
            generated_artifact_path=raw.get("generated_artifact_path"),
        )

    def get(self, change_id: str) -> ProposedDocumentChange | None:
        raw = self._load().get(change_id)
        return self._from_dict(raw) if raw else None

    def list(self, *, status: ChangeStatus | None = None) -> list[ProposedDocumentChange]:
        changes = [self._from_dict(item) for item in self._load().values()]
        if status is not None:
            changes = [item for item in changes if item.status == status]
        return sorted(changes, key=lambda item: item.created_at)

    def propose(
        self,
        *,
        document: DocumentReference,
        requested_by: str,
        reason: str,
        instructions: list[RedlineInstruction],
        proposed_revision: str | None = None,
    ) -> ProposedDocumentChange:
        if not instructions:
            raise DocumentChangeError("At least one redline instruction is required")
        change = ProposedDocumentChange(
            id=f"chg-{uuid4().hex}",
            document=document,
            requested_by=requested_by,
            reason=reason.strip(),
            instructions=instructions,
            created_at=self._now(),
            proposed_revision=proposed_revision,
        )
        payload = self._load()
        payload[change.id] = change.to_dict()
        self._save(payload)
        return change

    def submit_for_review(self, change_id: str, *, actor_id: str, comment: str = "") -> ProposedDocumentChange:
        change = self._require(change_id)
        if change.status != ChangeStatus.PROPOSED:
            raise DocumentChangeError("Only proposed changes can be submitted for review")
        change.status = ChangeStatus.IN_REVIEW
        change.events.append(ApprovalEvent(actor_id, "submit_for_review", self._now(), comment))
        return self._persist(change)

    def approve(self, change_id: str, *, actor_id: str, comment: str = "") -> ProposedDocumentChange:
        change = self._require(change_id)
        if change.status != ChangeStatus.IN_REVIEW:
            raise DocumentChangeError("A document change must be in review before approval")
        if actor_id.strip() == change.requested_by.strip():
            raise DocumentChangeError("Requester cannot self-approve a controlled engineering document change")
        change.status = ChangeStatus.APPROVED
        change.events.append(ApprovalEvent(actor_id, "approve", self._now(), comment))
        return self._persist(change)

    def reject(self, change_id: str, *, actor_id: str, comment: str = "") -> ProposedDocumentChange:
        change = self._require(change_id)
        if change.status not in {ChangeStatus.PROPOSED, ChangeStatus.IN_REVIEW}:
            raise DocumentChangeError("Approved or already rejected changes cannot be rejected")
        change.status = ChangeStatus.REJECTED
        change.events.append(ApprovalEvent(actor_id, "reject", self._now(), comment))
        return self._persist(change)

    def attach_generated_redline(self, change_id: str, *, artifact_path: str, actor_id: str = "assistant") -> ProposedDocumentChange:
        change = self._require(change_id)
        if change.status in {ChangeStatus.APPROVED, ChangeStatus.REJECTED}:
            raise DocumentChangeError("Closed document changes cannot receive new redline artifacts")
        change.generated_artifact_path = artifact_path
        change.events.append(ApprovalEvent(actor_id, "attach_redline", self._now(), artifact_path))
        return self._persist(change)

    def _require(self, change_id: str) -> ProposedDocumentChange:
        change = self.get(change_id)
        if change is None:
            raise DocumentChangeError(f"Unknown document change: {change_id}")
        return change

    def _persist(self, change: ProposedDocumentChange) -> ProposedDocumentChange:
        payload = self._load()
        payload[change.id] = change.to_dict()
        self._save(payload)
        return change
