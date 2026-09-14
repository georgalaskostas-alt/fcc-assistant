from __future__ import annotations

import pytest

from app.engineering_documents import (
    ChangeStatus,
    DocumentChangeError,
    DocumentReference,
    EngineeringDocumentWorkflow,
    RedlineInstruction,
)


def _document() -> DocumentReference:
    return DocumentReference(
        document_id="21-FCC-104",
        title="FCC P&ID 21-FCC-104",
        revision="7",
        document_type="pid",
        unit_key="fcc",
        equipment_keys=("E-202",),
    )


def test_document_change_requires_redline_instruction(tmp_path):
    workflow = EngineeringDocumentWorkflow(tmp_path / "changes.json")
    with pytest.raises(DocumentChangeError):
        workflow.propose(
            document=_document(),
            requested_by="engineer-a",
            reason="Correct drawing error",
            instructions=[],
        )


def test_controlled_change_requires_review_and_independent_approval(tmp_path):
    workflow = EngineeringDocumentWorkflow(tmp_path / "changes.json")
    change = workflow.propose(
        document=_document(),
        requested_by="engineer-a",
        reason="XV-204 connection is shown on the wrong side of E-202",
        instructions=[
            RedlineInstruction(
                description="Move XV-204 connection downstream of E-202",
                page=1,
                target_reference="XV-204",
                markup_kind="relocate",
            )
        ],
        proposed_revision="8",
    )

    assert change.status == ChangeStatus.PROPOSED

    with pytest.raises(DocumentChangeError):
        workflow.approve(change.id, actor_id="engineer-b")

    reviewed = workflow.submit_for_review(change.id, actor_id="engineer-a")
    assert reviewed.status == ChangeStatus.IN_REVIEW

    with pytest.raises(DocumentChangeError):
        workflow.approve(change.id, actor_id="engineer-a")

    approved = workflow.approve(change.id, actor_id="engineer-b", comment="Checked against field markup")
    assert approved.status == ChangeStatus.APPROVED
    assert approved.document.revision == "7"
    assert approved.proposed_revision == "8"
    assert approved.events[-1].action == "approve"


def test_generated_redline_is_non_destructive_and_audited(tmp_path):
    workflow = EngineeringDocumentWorkflow(tmp_path / "changes.json")
    change = workflow.propose(
        document=_document(),
        requested_by="engineer-a",
        reason="Instrument location correction",
        instructions=[RedlineInstruction(description="Relocate PT-302 upstream of control valve")],
    )

    updated = workflow.attach_generated_redline(
        change.id,
        artifact_path="/controlled-work/redlines/21-FCC-104-proposed.pdf",
    )

    assert updated.generated_artifact_path.endswith("21-FCC-104-proposed.pdf")
    assert updated.document.revision == "7"
    assert updated.status == ChangeStatus.PROPOSED
    assert updated.events[-1].action == "attach_redline"


def test_closed_change_cannot_be_mutated(tmp_path):
    workflow = EngineeringDocumentWorkflow(tmp_path / "changes.json")
    change = workflow.propose(
        document=_document(),
        requested_by="engineer-a",
        reason="Correction",
        instructions=[RedlineInstruction(description="Correct line annotation")],
    )
    workflow.submit_for_review(change.id, actor_id="engineer-a")
    workflow.approve(change.id, actor_id="engineer-b")

    with pytest.raises(DocumentChangeError):
        workflow.attach_generated_redline(change.id, artifact_path="/tmp/late.pdf")
