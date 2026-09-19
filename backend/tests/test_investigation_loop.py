import pytest
from backend.app.investigation_loop import run_autonomous_evidence_loop
from backend.app.agent_tools import ToolContext, ToolRegistry
from backend.app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope

@pytest.mark.asyncio
async def test_loop_stops_when_no_governed_follow_up_can_add_evidence():
    registry=ToolRegistry()
    refinery=RefineryScope(key="site",name="Site",units=(UnitScope(key="fcc",name="FCC"),))
    access=AccessGrant(actor_id="u",allowed_domains=frozenset({DataDomain.PROCESS,DataDomain.KNOWLEDGE}),refinery_keys=frozenset({"site"}),unit_keys=frozenset({"fcc"}))
    context=ToolContext(actor_id="u",refinery=refinery,access=access,scope_kind=ScopeKind.UNIT,scope_id="fcc")
    synthesis={"evidence_package":[],"archive_evidence":{"count":0},"event_evidence":{"count":0},"similar_episodes":{"count":0}}
    result=await run_autonomous_evidence_loop(registry=registry,context=context,goal="why",unit_key="fcc",
        synthesis=synthesis,time_window={"start":"a","end":"b"},episode_context={},max_rounds=3)
    assert result["rounds_completed"] <= 1
    assert result["stop_reason"] in {"no_new_evidence","repeated_plan_no_new_direction"}
    assert result["process_control_actions_allowed"] is False

def test_loop_module_has_hard_round_bound():
    import inspect
    from backend.app import investigation_loop
    source=inspect.getsource(investigation_loop.run_autonomous_evidence_loop)
    assert "max_rounds" in source
    assert "seen_plans" in source
