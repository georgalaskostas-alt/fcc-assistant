from dataclasses import dataclass

import pytest

from app.agent_tools import ToolContext, ToolEffect
from app.refinery_model import (
    AccessGrant,
    DataDomain,
    RefineryScope,
    ScopeKind,
    UnitScope,
)
from app.refinery_tools import build_refinery_tool_registry


class FakeTags:
    def search(self, query):
        return [{"key": "feed_flow", "query": query, "unit_key": "fcc"}]

    async def recorded_values(self, key, start_time, end_time, max_count=1000):
        return {"tag": key, "start": start_time, "end": end_time, "max_count": max_count}


class FakeArchive:
    def search(self, **kwargs):
        return []

    def document_context(self, record_id):
        return {"record_id": record_id}


@dataclass
class FakeRecord:
    document_id: str = "21-FCC-104"
    revision: str = "7"

    def to_dict(self):
        return {"document_id": self.document_id, "revision": self.revision, "approval_state": "approved"}


class FakeChange:
    def to_dict(self):
        return {"id": "chg-1", "status": "proposed", "requested_by": "engineer-1"}


class FakeEngineeringDocuments:
    def approved_master(self, document_id):
        return FakeRecord(document_id=document_id)

    def propose_against_approved(self, **kwargs):
        assert kwargs["requested_by"] == "engineer-1"
        assert kwargs["document_id"] == "21-FCC-104"
        return FakeChange()


def _context() -> ToolContext:
    refinery = RefineryScope(
        id="site-1",
        name="Refinery",
        standalone_units=(UnitScope("fcc", "FCC"),),
    )
    return ToolContext(
        actor_id="engineer-1",
        refinery=refinery,
        access=AccessGrant(
            domains=frozenset({DataDomain.PROCESS, DataDomain.KNOWLEDGE}),
            unit_ids=frozenset({"fcc"}),
        ),
        scope_kind=ScopeKind.UNIT,
        scope_id="fcc",
    )


def _registry():
    return build_refinery_tool_registry(
        tag_service=FakeTags(),
        archive=FakeArchive(),
        engineering_documents=FakeEngineeringDocuments(),
    )


def test_catalog_exposes_reads_and_proposals_but_not_human_approval_actions():
    registry = _registry()
    definitions = {item["name"]: item for item in registry.definitions()}

    assert "search_tags" in definitions
    assert "get_history" in definitions
    assert "search_archive" in definitions
    assert "find_approved_document" in definitions
    assert definitions["propose_document_change"]["effect"] == ToolEffect.CONTROLLED_DOCUMENT_PROPOSAL.value
    assert "approve_document_change" not in definitions
    assert "promote_document_revision" not in definitions
    assert not any("setpoint" in name or "valve" in name for name in definitions)


@pytest.mark.asyncio
async def test_agent_can_create_proposal_without_gaining_approval_power():
    registry = _registry()
    result = await registry.execute(
        "propose_document_change",
        context=_context(),
        arguments={
            "document_id": "21-FCC-104",
            "reason": "Correct drawing error",
            "proposed_revision": "8",
            "instructions": [
                {
                    "description": "Move PT-302 to the correct process connection",
                    "page": 1,
                    "target_reference": "PT-302",
                    "markup_kind": "relocate",
                }
            ],
        },
    )

    assert result.ok is True
    assert result.effect == ToolEffect.CONTROLLED_DOCUMENT_PROPOSAL
    assert result.data["status"] == "proposed"
    assert result.data["requested_by"] == "engineer-1"


@pytest.mark.asyncio
async def test_history_tool_remains_read_only():
    registry = _registry()
    result = await registry.execute(
        "get_history",
        context=_context(),
        arguments={
            "tag_key": "feed_flow",
            "start_time": "2026-09-14T00:00:00Z",
            "end_time": "2026-09-14T08:00:00Z",
        },
    )

    assert result.effect == ToolEffect.READ_ONLY
    assert result.data["tag"] == "feed_flow"


class CrossUnitTags(FakeTags):
    def search(self, query):
        if query=="hcu_feed": return [{"key":"hcu_feed","unit_key":"hcu"}]
        return [{"key":"feed_flow","unit_key":"fcc"},{"key":"hcu_feed","unit_key":"hcu"}]

@pytest.mark.asyncio
async def test_search_tags_filters_foreign_units():
    registry=build_refinery_tool_registry(tag_service=CrossUnitTags(),archive=FakeArchive(),engineering_documents=FakeEngineeringDocuments())
    result=await registry.execute("search_tags",context=_context(),arguments={"query":"feed"})
    assert [row["unit_key"] for row in result.data]==["fcc"]

@pytest.mark.asyncio
async def test_history_rejects_foreign_unit_tag():
    registry=build_refinery_tool_registry(tag_service=CrossUnitTags(),archive=FakeArchive(),engineering_documents=FakeEngineeringDocuments())
    with pytest.raises(Exception):
        await registry.execute("get_history",context=_context(),arguments={"tag_key":"hcu_feed","start_time":"a","end_time":"b"})

@pytest.mark.asyncio
async def test_archive_rejects_foreign_unit_argument():
    registry=_registry()
    with pytest.raises(Exception):
        await registry.execute("search_archive",context=_context(),arguments={"query":"compressor","unit_key":"hcu"})
