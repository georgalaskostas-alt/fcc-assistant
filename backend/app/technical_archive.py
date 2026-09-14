"""Governed technical archive facade.

Combines document metadata/revision control with local text ingestion and search.
Search results retain document identity, revision and provenance so higher layers
can cite the exact engineering source used for an answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .document_registry import (
    ApprovalState,
    DocumentRecord,
    DocumentRegistry,
    DocumentRegistryError,
    DocumentType,
    EngineeringLinks,
)
from .manual_ingestion import ManualIngestionError, ingest_manual, search_manual_index


class TechnicalArchiveError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArchiveSearchHit:
    record_id: str
    document_id: str
    title: str
    document_type: str
    revision: str
    approval_state: str
    page: int | None
    text: str
    score: int
    source_system: str
    source_path: str
    unit_keys: tuple[str, ...]
    equipment_keys: tuple[str, ...]


class TechnicalArchive:
    """Local technical archive with revision-aware, source-grounded retrieval."""

    def __init__(
        self,
        *,
        registry: DocumentRegistry | None = None,
        manual_root: Path | None = None,
    ) -> None:
        self.registry = registry or DocumentRegistry()
        self.manual_root = manual_root

    def ingest_text_document(
        self,
        *,
        document_id: str,
        title: str,
        document_type: DocumentType,
        revision: str,
        approval_state: ApprovalState,
        filename: str,
        data: bytes,
        unit_key: str,
        source_system: str,
        source_path: str,
        imported_by: str,
        equipment_keys: tuple[str, ...] = (),
        checksum: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> DocumentRecord:
        """Ingest searchable content and register its controlled metadata.

        If registry creation fails, the source master is still never modified;
        only the local searchable copy may have been created. Callers can safely
        retry with corrected metadata after resolving the registry conflict.
        """

        try:
            ingested = ingest_manual(unit_key, filename, data, root=self.manual_root)
            return self.registry.register(
                document_id=document_id,
                title=title,
                document_type=document_type,
                revision=revision,
                approval_state=approval_state,
                source_system=source_system,
                source_path=source_path,
                imported_by=imported_by,
                checksum=checksum,
                links=EngineeringLinks(
                    unit_keys=(unit_key.casefold(),),
                    equipment_keys=equipment_keys,
                ),
                page_count=ingested.pages,
                metadata={
                    **(metadata or {}),
                    "local_storage_id": ingested.storage_id,
                    "local_index_path": ingested.index_path,
                    "local_stored_path": ingested.stored_path,
                },
            )
        except (ManualIngestionError, DocumentRegistryError) as exc:
            raise TechnicalArchiveError(str(exc)) from exc

    def search(
        self,
        *,
        query: str,
        unit_key: str,
        limit: int = 8,
        approved_only: bool = True,
        document_type: DocumentType | None = None,
        equipment_key: str | None = None,
    ) -> list[ArchiveSearchHit]:
        candidates = self.registry.list(
            document_type=document_type,
            approval_state=ApprovalState.APPROVED if approved_only else None,
            unit_key=unit_key,
            equipment_key=equipment_key,
        )
        by_storage_id: dict[str, DocumentRecord] = {}
        for record in candidates:
            storage_id = record.metadata.get("local_storage_id")
            if storage_id:
                by_storage_id[storage_id] = record

        if not by_storage_id:
            return []

        raw_hits = search_manual_index(unit_key, query, limit=max(limit * 3, limit), root=self.manual_root)
        results: list[ArchiveSearchHit] = []
        for hit in raw_hits:
            storage_id = str(hit.get("manual_storage_id") or "")
            record = by_storage_id.get(storage_id)
            if record is None:
                continue
            results.append(
                ArchiveSearchHit(
                    record_id=record.record_id,
                    document_id=record.document_id,
                    title=record.title,
                    document_type=record.document_type.value,
                    revision=record.revision,
                    approval_state=record.approval_state.value,
                    page=hit.get("page") if isinstance(hit.get("page"), int) else None,
                    text=str(hit.get("text") or ""),
                    score=int(hit.get("score") or 0),
                    source_system=record.provenance.source_system,
                    source_path=record.provenance.source_path,
                    unit_keys=record.links.unit_keys,
                    equipment_keys=record.links.equipment_keys,
                )
            )
            if len(results) >= max(1, min(limit, 25)):
                break
        return results

    def document_context(self, record_id: str) -> dict[str, Any]:
        record = self.registry.get(record_id)
        if record is None:
            raise TechnicalArchiveError(f"Unknown document record: {record_id}")
        return {
            "record_id": record.record_id,
            "document_id": record.document_id,
            "title": record.title,
            "document_type": record.document_type.value,
            "revision": record.revision,
            "approval_state": record.approval_state.value,
            "source_system": record.provenance.source_system,
            "source_path": record.provenance.source_path,
            "unit_keys": list(record.links.unit_keys),
            "equipment_keys": list(record.links.equipment_keys),
            "tag_keys": list(record.links.tag_keys),
            "metadata": dict(record.metadata),
        }
