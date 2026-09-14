from pathlib import Path

import pytest

from app.document_registry import (
    ApprovalState,
    DocumentRegistry,
    DocumentRegistryError,
    DocumentType,
    EngineeringLinks,
)


def _registry(tmp_path: Path) -> DocumentRegistry:
    return DocumentRegistry(tmp_path / "registry.json")


def test_registers_revision_with_provenance_and_engineering_links(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    record = registry.register(
        document_id="21-FCC-104",
        title="FCC Reactor / Regenerator P&ID",
        document_type=DocumentType.PID,
        revision="A",
        approval_state=ApprovalState.APPROVED,
        source_system="technical-archive",
        source_path="/approved/21-FCC-104_revA.pdf",
        imported_by="engineer-1",
        checksum="sha256:abc",
        links=EngineeringLinks(
            refinery_id="aspropyrgos",
            unit_keys=("fcc",),
            equipment_keys=("reactor", "regenerator"),
            tag_keys=("pt-302",),
        ),
        page_count=3,
    )

    assert record.document_id == "21-FCC-104"
    assert record.revision == "A"
    assert record.provenance.source_system == "technical-archive"
    assert record.links.unit_keys == ("fcc",)
    assert registry.approved_revision("21-FCC-104") == record
    assert registry.list(unit_key="FCC") == [record]
    assert registry.list(equipment_key="REACTOR") == [record]


def test_duplicate_document_revision_is_rejected(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    kwargs = dict(
        document_id="21-FCC-104",
        title="P&ID",
        document_type=DocumentType.PID,
        revision="A",
        approval_state=ApprovalState.APPROVED,
        source_system="archive",
        source_path="/a.pdf",
    )
    registry.register(**kwargs)

    with pytest.raises(DocumentRegistryError, match="already registered"):
        registry.register(**kwargs)


def test_new_revision_requires_explicit_supersession_before_approval(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    old = registry.register(
        document_id="21-FCC-104",
        title="P&ID",
        document_type=DocumentType.PID,
        revision="A",
        approval_state=ApprovalState.APPROVED,
        source_system="archive",
        source_path="/revA.pdf",
    )
    new = registry.register(
        document_id="21-FCC-104",
        title="P&ID",
        document_type=DocumentType.PID,
        revision="B",
        approval_state=ApprovalState.FOR_REVIEW,
        source_system="engineering-workspace",
        source_path="/revB-redline.pdf",
    )

    with pytest.raises(DocumentRegistryError, match="explicit supersession"):
        registry.set_approval_state(new.record_id, ApprovalState.APPROVED)

    approved = registry.set_approval_state(
        new.record_id,
        ApprovalState.APPROVED,
        supersede_previous_approved=True,
    )

    assert approved.approval_state == ApprovalState.APPROVED
    assert registry.get(old.record_id).approval_state == ApprovalState.SUPERSEDED
    assert registry.approved_revision("21-FCC-104").record_id == new.record_id


def test_approved_master_is_not_overwritten_by_registration(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    master = registry.register(
        document_id="FCC-OM-001",
        title="FCC Operating Manual",
        document_type=DocumentType.MANUAL,
        revision="4",
        approval_state=ApprovalState.APPROVED,
        source_system="controlled-archive",
        source_path="/manual-r4.pdf",
    )
    draft = registry.register(
        document_id="FCC-OM-001",
        title="FCC Operating Manual",
        document_type=DocumentType.MANUAL,
        revision="5-draft",
        approval_state=ApprovalState.DRAFT,
        source_system="assistant-workspace",
        source_path="/manual-r5-draft.pdf",
    )

    assert registry.approved_revision("FCC-OM-001").record_id == master.record_id
    assert draft.approval_state == ApprovalState.DRAFT
    assert registry.get(master.record_id).provenance.source_path == "/manual-r4.pdf"
