from pathlib import Path

import pytest

from app.document_registry import (
    ApprovalState,
    DocumentRegistry,
    DocumentType,
    EngineeringLinks,
)
from app.engineering_document_service import (
    EngineeringDocumentService,
    EngineeringDocumentServiceError,
)
from app.engineering_documents import EngineeringDocumentWorkflow, RedlineInstruction


def _service(tmp_path: Path) -> EngineeringDocumentService:
    registry = DocumentRegistry(tmp_path / "registry.json")
    workflow = EngineeringDocumentWorkflow(tmp_path / "changes.json")
    registry.register(
        document_id="21-FCC-104",
        title="FCC Reactor / Regenerator P&ID",
        document_type=DocumentType.PID,
        revision="7",
        approval_state=ApprovalState.APPROVED,
        source_system="technical-archive",
        source_path="/approved/21-FCC-104-rev7.pdf",
        links=EngineeringLinks(
            refinery_id="aspropyrgos",
            unit_keys=("fcc",),
            equipment_keys=("reactor", "regenerator"),
            tag_keys=("pt-302",),
        ),
    )
    return EngineeringDocumentService(registry=registry, workflow=workflow)


def test_proposal_binds_to_exact_approved_master(tmp_path: Path) -> None:
    service = _service(tmp_path)

    change = service.propose_against_approved(
        document_id="21-FCC-104",
        requested_by="engineer-a",
        reason="Correct instrument position",
        instructions=[
            RedlineInstruction(
                description="Relocate PT-302 upstream of the control valve",
                page=1,
                target_reference="PT-302",
                markup_kind="relocate",
            )
        ],
        proposed_revision="8",
    )

    assert change.document.document_id == "21-FCC-104"
    assert change.document.revision == "7"
    assert change.document.source_path == "/approved/21-FCC-104-rev7.pdf"
    assert change.proposed_revision == "8"


def test_promotion_requires_review_approval_and_artifact(tmp_path: Path) -> None:
    service = _service(tmp_path)
    change = service.propose_against_approved(
        document_id="21-FCC-104",
        requested_by="engineer-a",
        reason="Drawing correction",
        instructions=[RedlineInstruction(description="Correct line connection")],
        proposed_revision="8",
    )

    with pytest.raises(EngineeringDocumentServiceError, match="independently approved"):
        service.promote_approved_change(change.id, actor_id="document-controller")

    service.submit_for_review(change.id, actor_id="engineer-a")
    service.approve(change.id, actor_id="engineer-b")

    with pytest.raises(EngineeringDocumentServiceError, match="no generated"):
        service.promote_approved_change(change.id, actor_id="document-controller")


def test_approved_redline_can_be_promoted_to_new_master(tmp_path: Path) -> None:
    service = _service(tmp_path)
    change = service.propose_against_approved(
        document_id="21-FCC-104",
        requested_by="engineer-a",
        reason="Correct PT-302 location",
        instructions=[RedlineInstruction(description="Move PT-302 upstream")],
        proposed_revision="8",
    )
    service.attach_redline(
        change.id,
        artifact_path="/controlled-work/21-FCC-104-rev8.pdf",
    )
    service.submit_for_review(change.id, actor_id="engineer-a")
    service.approve(change.id, actor_id="engineer-b")

    result = service.promote_approved_change(
        change.id,
        actor_id="document-controller",
        checksum="sha256:new",
    )

    assert result.previous_master.revision == "7"
    assert result.new_master.revision == "8"
    assert result.new_master.approval_state == ApprovalState.APPROVED
    assert result.new_master.provenance.source_path.endswith("rev8.pdf")
    assert result.new_master.metadata["promoted_from_change_id"] == change.id
    assert service.registry.get(result.previous_master.record_id).approval_state == ApprovalState.SUPERSEDED
    assert service.registry.approved_revision("21-FCC-104").revision == "8"


def test_stale_proposal_cannot_supersede_newer_master(tmp_path: Path) -> None:
    service = _service(tmp_path)
    change = service.propose_against_approved(
        document_id="21-FCC-104",
        requested_by="engineer-a",
        reason="Old proposal",
        instructions=[RedlineInstruction(description="Old correction")],
        proposed_revision="8",
    )
    service.attach_redline(change.id, artifact_path="/controlled-work/old-rev8.pdf")
    service.submit_for_review(change.id, actor_id="engineer-a")
    service.approve(change.id, actor_id="engineer-b")

    newer = service.registry.register(
        document_id="21-FCC-104",
        title="FCC Reactor / Regenerator P&ID",
        document_type=DocumentType.PID,
        revision="7A",
        approval_state=ApprovalState.FOR_REVIEW,
        source_system="technical-archive",
        source_path="/approved/21-FCC-104-rev7A.pdf",
    )
    service.registry.set_approval_state(
        newer.record_id,
        ApprovalState.APPROVED,
        supersede_previous_approved=True,
    )

    with pytest.raises(EngineeringDocumentServiceError, match="rebase/review"):
        service.promote_approved_change(change.id, actor_id="document-controller")


def test_proposed_revision_must_be_new(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(EngineeringDocumentServiceError, match="differ"):
        service.propose_against_approved(
            document_id="21-FCC-104",
            requested_by="engineer-a",
            reason="No-op",
            instructions=[RedlineInstruction(description="No-op")],
            proposed_revision="7",
        )
