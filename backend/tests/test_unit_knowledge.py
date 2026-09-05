from pathlib import Path

from app.unit_knowledge import UnitKnowledgeStore


def test_effective_context_keeps_manual_and_current_override_separate(tmp_path: Path) -> None:
    store = UnitKnowledgeStore(tmp_path / "knowledge.json")

    manual = store.add_manual(
        "fcc",
        title="FCC Operating Manual",
        revision="R3",
        source_path="/local/manuals/fcc-r3.pdf",
        summary="Approved operating manual summary",
        document_date="2024-01-15",
        status="approved",
    )
    override = store.add_override(
        "fcc",
        subject="FV-123 normal maximum opening",
        manual_value="65%",
        current_value="60%",
        reason="Post-revamp hydraulic limitation",
        manual_reference="Section 4.2, page 118",
        effective_from="2025-06-01T00:00:00Z",
        approved_by="Process Engineering",
        status="approved",
    )
    store.set_knowledge_status("fcc", "approved")

    context = store.effective_context("fcc", "2026-08-23T08:00:00Z")

    assert context["knowledge_status"] == "approved"
    assert context["manuals"][0]["id"] == manual["id"]
    assert context["manuals"][0]["summary"] == "Approved operating manual summary"
    assert context["overrides"][0]["id"] == override["id"]
    assert context["overrides"][0]["manual_value"] == "65%"
    assert context["overrides"][0]["current_value"] == "60%"
    assert context["read_only_process_access"] is True


def test_historical_context_does_not_apply_future_override(tmp_path: Path) -> None:
    store = UnitKnowledgeStore(tmp_path / "knowledge.json")
    store.add_override(
        "fcc",
        subject="FV-123 normal maximum opening",
        manual_value="65%",
        current_value="60%",
        reason="Post-revamp hydraulic limitation",
        effective_from="2025-06-01T00:00:00Z",
        status="approved",
    )

    before = store.effective_context("fcc", "2025-05-01T00:00:00Z")
    after = store.effective_context("fcc", "2025-07-01T00:00:00Z")

    assert before["overrides"] == []
    assert len(after["overrides"]) == 1


def test_draft_records_are_not_used_as_effective_operational_knowledge(tmp_path: Path) -> None:
    store = UnitKnowledgeStore(tmp_path / "knowledge.json")
    store.add_revamp(
        "hcu",
        title="Reactor internals revamp",
        description="Updated reactor internals and operating envelope.",
        effective_from="2026-01-01T00:00:00Z",
        status="draft",
    )
    store.add_override(
        "hcu",
        subject="Hydrogen/oil ratio guidance",
        manual_value="manual basis",
        current_value="current engineering basis",
        reason="Awaiting engineering approval",
        effective_from="2026-01-01T00:00:00Z",
        status="draft",
    )

    context = store.effective_context("hcu", "2026-08-23T00:00:00Z")

    assert context["revamps"] == []
    assert context["overrides"] == []
