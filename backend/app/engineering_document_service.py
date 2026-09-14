"""Bridge controlled engineering changes to the technical document registry.

This service binds every AI-assisted/redline proposal to the exact approved
master revision that existed when the proposal was created. Promotion is
refused if that baseline is no longer current, preventing stale changes from
silently superseding a newer approved engineering document.
"""

from __future__ import annotations

from dataclasses import dataclass

from .document_registry import (
    ApprovalState,
    DocumentRecord,
    DocumentRegistry,
    DocumentRegistryError,
    DocumentType,
    EngineeringLinks,
)
from .engineering_documents import (
    ChangeStatus,
    DocumentChangeError,
    DocumentReference,
    EngineeringDocumentWorkflow,
    ProposedDocumentChange,
    RedlineInstruction,
)


class EngineeringDocumentServiceError(ValueError):
    pass


@dataclass(frozen=True)
class PromotionResult:
    change: ProposedDocumentChange
    previous_master: DocumentRecord
    new_master: DocumentRecord


class EngineeringDocumentService:
    """Controlled workflow facade for archive-backed engineering revisions."""

    def __init__(
        self,
        *,
        registry: DocumentRegistry | None = None,
        workflow: EngineeringDocumentWorkflow | None = None,
    ) -> None:
        self.registry = registry or DocumentRegistry()
        self.workflow = workflow or EngineeringDocumentWorkflow()

    @staticmethod
    def _reference(record: DocumentRecord) -> DocumentReference:
        unit_key = record.links.unit_keys[0] if len(record.links.unit_keys) == 1 else None
        return DocumentReference(
            document_id=record.document_id,
            title=record.title,
            revision=record.revision,
            document_type=record.document_type.value,
            source_path=record.provenance.source_path,
            unit_key=unit_key,
            equipment_keys=record.links.equipment_keys,
        )

    def approved_master(self, document_id: str) -> DocumentRecord:
        try:
            record = self.registry.approved_revision(document_id)
        except DocumentRegistryError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc
        if record is None:
            raise EngineeringDocumentServiceError(
                f"No approved master revision is registered for {document_id}"
            )
        return record

    def propose_against_approved(
        self,
        *,
        document_id: str,
        requested_by: str,
        reason: str,
        instructions: list[RedlineInstruction],
        proposed_revision: str,
    ) -> ProposedDocumentChange:
        revision = proposed_revision.strip()
        if not revision:
            raise EngineeringDocumentServiceError("proposed_revision is required")

        master = self.approved_master(document_id)
        if master.revision.casefold() == revision.casefold():
            raise EngineeringDocumentServiceError(
                "Proposed revision must differ from the approved master revision"
            )
        if self.registry.find_revision(master.document_id, revision) is not None:
            raise EngineeringDocumentServiceError(
                f"Revision {revision} is already registered for {master.document_id}"
            )

        try:
            return self.workflow.propose(
                document=self._reference(master),
                requested_by=requested_by,
                reason=reason,
                instructions=instructions,
                proposed_revision=revision,
            )
        except DocumentChangeError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc

    def submit_for_review(
        self,
        change_id: str,
        *,
        actor_id: str,
        comment: str = "",
    ) -> ProposedDocumentChange:
        try:
            return self.workflow.submit_for_review(change_id, actor_id=actor_id, comment=comment)
        except DocumentChangeError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc

    def approve(
        self,
        change_id: str,
        *,
        actor_id: str,
        comment: str = "",
    ) -> ProposedDocumentChange:
        try:
            return self.workflow.approve(change_id, actor_id=actor_id, comment=comment)
        except DocumentChangeError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc

    def attach_redline(
        self,
        change_id: str,
        *,
        artifact_path: str,
        actor_id: str = "assistant",
    ) -> ProposedDocumentChange:
        try:
            return self.workflow.attach_generated_redline(
                change_id,
                artifact_path=artifact_path,
                actor_id=actor_id,
            )
        except DocumentChangeError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc

    def promote_approved_change(
        self,
        change_id: str,
        *,
        actor_id: str,
        checksum: str | None = None,
        source_system: str = "engineering-workspace",
    ) -> PromotionResult:
        change = self.workflow.get(change_id)
        if change is None:
            raise EngineeringDocumentServiceError(f"Unknown document change: {change_id}")
        if change.status != ChangeStatus.APPROVED:
            raise EngineeringDocumentServiceError(
                "Only an independently approved document change can be promoted"
            )
        if not change.proposed_revision:
            raise EngineeringDocumentServiceError("Approved change has no proposed revision")
        if not change.generated_artifact_path:
            raise EngineeringDocumentServiceError(
                "Approved change has no generated redline/revision artifact"
            )

        current_master = self.approved_master(change.document.document_id)
        if current_master.revision.casefold() != change.document.revision.casefold():
            raise EngineeringDocumentServiceError(
                "Approved master changed after this proposal was created; rebase/review is required"
            )

        existing = self.registry.find_revision(
            change.document.document_id,
            change.proposed_revision,
        )
        if existing is not None:
            raise EngineeringDocumentServiceError(
                f"Revision {change.proposed_revision} is already registered"
            )

        try:
            candidate = self.registry.register(
                document_id=current_master.document_id,
                title=current_master.title,
                document_type=DocumentType(current_master.document_type.value),
                revision=change.proposed_revision,
                approval_state=ApprovalState.FOR_REVIEW,
                source_system=source_system,
                source_path=change.generated_artifact_path,
                imported_by=actor_id,
                checksum=checksum,
                links=EngineeringLinks(
                    refinery_id=current_master.links.refinery_id,
                    complex_keys=current_master.links.complex_keys,
                    unit_keys=current_master.links.unit_keys,
                    equipment_keys=current_master.links.equipment_keys,
                    stream_keys=current_master.links.stream_keys,
                    tag_keys=current_master.links.tag_keys,
                ),
                language=current_master.language,
                page_count=current_master.page_count,
                metadata={
                    **current_master.metadata,
                    "promoted_from_change_id": change.id,
                    "baseline_revision": current_master.revision,
                },
            )
            new_master = self.registry.set_approval_state(
                candidate.record_id,
                ApprovalState.APPROVED,
                supersede_previous_approved=True,
            )
        except DocumentRegistryError as exc:
            raise EngineeringDocumentServiceError(str(exc)) from exc

        return PromotionResult(
            change=change,
            previous_master=current_master,
            new_master=new_master,
        )
