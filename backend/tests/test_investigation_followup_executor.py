import pytest
from backend.app.agent_tools import ToolContext, ToolDefinition, ToolEffect, ToolParameter, ToolRegistry
from backend.app.investigation_followup_executor import execute_follow_up
from backend.app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope

@pytest.mark.asyncio
async def test_follow_up_executes_only_read_only_tools():
    registry=ToolRegistry()
    registry.register(ToolDefinition(name="search_archive",description="",domain=DataDomain.KNOWLEDGE,effect=ToolEffect.READ_ONLY,
        parameters=(ToolParameter("query","string"),ToolParameter("unit_key","string"),ToolParameter("approved_only","boolean"),ToolParameter("limit","integer"))),
        lambda _c,_a:[{"document_id":"M1"}])
    refinery=RefineryScope(id="site",name="Site",standalone_units=(UnitScope(id="fcc",name="FCC"),))
    access=AccessGrant(domains=frozenset({DataDomain.KNOWLEDGE}),unit_ids=frozenset({"fcc"}))
    context=ToolContext(actor_id="u",refinery=refinery,access=access,scope_kind=ScopeKind.UNIT,scope_id="fcc")
    result=await execute_follow_up(registry=registry,context=context,goal="why",
        plan={"actions":[{"tool":"search_archive","arguments":{"query":"why","unit_key":"fcc","approved_only":True,"limit":8}}]},
        time_window={"start":"a","end":"b"},episode_context={})
    assert result["attempted"] is True
    assert result["evidence_package"][0]["tool"] == "search_archive"
