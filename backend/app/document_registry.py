"""Technical archive registry with revision, provenance and engineering links.

The registry is deliberately independent from document parsing/search. It is the
canonical metadata layer for manuals, P&IDs, PFDs, datasheets, procedures and
other controlled engineering records. Binary/source files remain in their
approved storage location; this module stores identities and provenance only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class DocumentType(StrEnum):
    PID = "pid"
    PFD = "pfd"
    MANUAL = "manual"
    DATASHEET = "datasheet"
    PROCEDURE = "procedure"
    LINE_LIST = "line_list"
    INSTRUMENT_LIST = "instrument_list"
    CAUSE_EFFECT = "cause_effect"
    CONTROL_NARRATIVE = "control_narrative"
    HAZOP = "hazop"
    MOC = "moc"
    INCIDENT_REPORT = "incident_report"
    INSPECTION_REPORT = "inspection_report"
    STUDY = "study"
    VENDOR_DOCUMENT = "vendor_document"
    TECHNICAL_NOTE = "technical_note"
    OTHER = "other"


class ApprovalState(StrEnum):
    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True)
class DocumentProvenance:
    source_system: str
    source_path: str
    imported_at: str
    imported_by: str = "system"
    checksum: str | None = None


@dataclass(frozen=True)
class EngineeringLinks:
    refinery_id: str | None = None
    complex_keys: tuple[str, ...] = ()
    unit_keys: tuple[str, ...] = ()
    equipment_keys: tuple[str, ...] = ()
    stream_keys: tuple[str, ...] = ()
    tag_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentRecord:
    record_id: str
    document_id: str
    title: str
    document_type: DocumentType
    revision: str
    approval_state: ApprovalState
    provenance: DocumentProvenance
    links: EngineeringLinks = field(default_factory=EngineeringLinks)
    issue_date: str | None = None
    effective_date: str | None = None
    language: str | None = None
    page_count: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["document_type"] = self.document_type.value
        payload["approval_state"] = self.approval_state.value
        return payload


class DocumentRegistryError(ValueError):
    pass


class DocumentRegistry:
    """Durable metadata registry for the refinery technical archive.

    A document may have many revisions but a `(document_id, revision)` pair is
    unique. Approved masters are never replaced by registration side effects;
    supersession is explicit and auditable through registry state.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".fcc-assistant" / "document-registry.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DocumentRegistryError(f"Could not read document registry: {exc}") from exc
        if not isinstance(raw, dict):
            raise DocumentRegistryError("Document registry root must be an object")
        return raw

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> DocumentRecord:
        provenance_raw = raw.get("provenance") or {}
        links_raw = raw.get("links") or {}
        return DocumentRecord(
            record_id=str(raw["record_id"]),
            document_id=str(raw["document_id"]),
            title=str(raw.get("title") or raw["document_id"]),
            document_type=DocumentType(str(raw.get("document_type") or DocumentType.OTHER.value)),
            revision=str(raw.get("revision") or ""),
            approval_state=ApprovalState(str(raw.get("approval_state") or ApprovalState.DRAFT.value)),
            provenance=DocumentProvenance(
                source_system=str(provenance_raw.get("source_system") or "unknown"),
                source_path=str(provenance_raw.get("source_path") or ""),
                imported_at=str(provenance_raw.get("imported_at") or ""),
                imported_by=str(provenance_raw.get("imported_by") or "system"),
                checksum=provenance_raw.get("checksum"),
            ),
            links=EngineeringLinks(
                refinery_id=links_raw.get("refinery_id"),
                complex_keys=tuple(links_raw.get("complex_keys") or ()),
                unit_keys=tuple(links_raw.get("unit_keys") or ()),
                equipment_keys=tuple(links_raw.get("equipment_keys") or ()),
                stream_keys=tuple(links_raw.get("stream_keys") or ()),
                tag_keys=tuple(links_raw.get("tag_keys") or ()),
            ),
            issue_date=raw.get("issue_date"),
            effective_date=raw.get("effective_date"),
            language=raw.get("language"),
            page_count=raw.get("page_count"),
            metadata={str(k): str(v) for k, v in (raw.get("metadata") or {}).items()},
        )

    def register(
        self,
        *,
        document_id: str,
        title: str,
        document_type: DocumentType,
        revision: str,
        approval_state: ApprovalState,
        source_system: str,
        source_path: str,
        imported_by: str = "system",
        checksum: str | None = None,
        links: EngineeringLinks | None = None,
        issue_date: str | None = None,
        effective_date: str | None = None,
        language: str | None = None,
        page_count: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> DocumentRecord:
        doc_id = document_id.strip()
        rev = revision.strip()
        if not doc_id:
            raise DocumentRegistryError("document_id is required")
        if not rev:
            raise DocumentRegistryError("revision is required")
        if not source_path.strip():
            raise DocumentRegistryError("source_path is required")

        existing = self.find_revision(doc_id, rev)
        if existing is not None:
            raise DocumentRegistryError(f"Document revision already registered: {doc_id} rev {rev}")

        record = DocumentRecord(
            record_id=f"doc-{uuid4().hex}",
            document_id=doc_id,
            title=title.strip() or doc_id,
            document_type=document_type,
            revision=rev,
            approval_state=approval_state,
            provenance=DocumentProvenance(
                source_system=source_system.strip() or "unknown",
                source_path=source_path.strip(),
                imported_at=self._now(),
                imported_by=imported_by.strip() or "system",
                checksum=checksum,
            ),
            links=links or EngineeringLinks(),
            issue_date=issue_date,
            effective_date=effective_date,
            language=language,
            page_count=page_count,
            metadata=metadata or {},
        )
        payload = self._load()
        payload[record.record_id] = record.to_dict()
        self._save(payload)
        return record

    def get(self, record_id: str) -> DocumentRecord | None:
        raw = self._load().get(record_id)
        return self._from_dict(raw) if raw else None

    def list(
        self,
        *,
        document_type: DocumentType | None = None,
        approval_state: ApprovalState | None = None,
        unit_key: str | None = None,
        equipment_key: str | None = None,
    ) -> list[DocumentRecord]:
        records = [self._from_dict(raw) for raw in self._load().values()]
        if document_type is not None:
            records = [item for item in records if item.document_type == document_type]
        if approval_state is not None:
            records = [item for item in records if item.approval_state == approval_state]
        if unit_key is not None:
            needle = unit_key.casefold()
            records = [item for item in records if needle in {value.casefold() for value in item.links.unit_keys}]
        if equipment_key is not None:
            needle = equipment_key.casefold()
            records = [item for item in records if needle in {value.casefold() for value in item.links.equipment_keys}]
        return sorted(records, key=lambda item: (item.document_id.casefold(), item.revision.casefold()))

    def revisions(self, document_id: str) -> list[DocumentRecord]:
        needle = document_id.strip().casefold()
        return [item for item in self.list() if item.document_id.casefold() == needle]

    def find_revision(self, document_id: str, revision: str) -> DocumentRecord | None:
        doc_needle = document_id.strip().casefold()
        rev_needle = revision.strip().casefold()
        return next(
            (
                item
                for item in self.list()
                if item.document_id.casefold() == doc_needle and item.revision.casefold() == rev_needle
            ),
            None,
        )

    def approved_revision(self, document_id: str) -> DocumentRecord | None:
        approved = [
            item
            for item in self.revisions(document_id)
            if item.approval_state == ApprovalState.APPROVED
        ]
        if len(approved) > 1:
            raise DocumentRegistryError(
                f"Multiple approved revisions registered for {document_id}; registry requires reconciliation"
            )
        return approved[0] if approved else None

    def set_approval_state(
        self,
        record_id: str,
        state: ApprovalState,
        *,
        supersede_previous_approved: bool = False,
    ) -> DocumentRecord:
        record = self.get(record_id)
        if record is None:
            raise DocumentRegistryError(f"Unknown document record: {record_id}")

        payload = self._load()
        if state == ApprovalState.APPROVED:
            prior = self.approved_revision(record.document_id)
            if prior is not None and prior.record_id != record.record_id:
                if not supersede_previous_approved:
                    raise DocumentRegistryError(
                        "Another approved revision exists; explicit supersession is required"
                    )
                prior_raw = payload[prior.record_id]
                prior_raw["approval_state"] = ApprovalState.SUPERSEDED.value

        current_raw = payload[record.record_id]
        current_raw["approval_state"] = state.value
        self._save(payload)
        updated = self.get(record.record_id)
        if updated is None:
            raise DocumentRegistryError("Registry update failed")
        return updated
