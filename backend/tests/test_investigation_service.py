import pytest

from app.agent_runtime import AgentPlan, step
from app.agent_tools import ToolContext, ToolDefinition, ToolEffect, ToolRegistry, ToolResult
from app.investigation_service import InvestigationService
from app.investigation_store import InvestigationStatus, InvestigationStore
from app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope


@pytest.mark.asyncio
async def test_persists_tool_evidence_across_investigation_run(tmp_path):
    registry = ToolRegistry()

    async def history(arguments, context):
        return ToolResult(
            data={"tag": {"key": "regenerator_dp", "name": "Regenerator DP"}, "data": [1, 2, 3]},
            provenance={"source_system": "PI", "read_only": True},
        )

    registry.register(
        ToolDefinition(
            name="get_history",
            description="read historian",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
            handler=history,
        )
    )

    refinery = RefineryScope(id="site", name="Site", standalone_units=(UnitScope("fcc", "FCC"),))
    context = ToolContext(
        user_id="engineer-1",
        refinery=refinery,
        grant=AccessGrant(domains=frozenset({DataDomain.PROCESS}), unit_ids=frozenset({"fcc"})),
        scope_kind=ScopeKind.UNIT,
        scope_id="fcc",
    )
    store = InvestigationStore(tmp_path / "investigations.json")
    service = InvestigationService(registry=registry, store=store)
    plan = AgentPlan(
        goal="Why did regenerator DP increase?",
        steps=(step("get_history", {"tag_key": "regenerator_dp"}, step_id="history"),),
    )

    result = await service.start(
        goal=plan.goal,
        user_id="engineer-1",
        unit_key="fcc",
        plan=plan,
        context=context,
    )

    persisted = store.get(result.investigation.id)
    assert persisted is not None
    assert persisted.status == InvestigationStatus.RUNNING
    assert persisted.plan_id == plan.plan_id
    assert len(persisted.evidence) == 1
    assert persisted.evidence[0].provenance["read_only"] is True

    completed = service.finish(persisted.id, conclusion="DP increased with the observed operating change.")
    assert completed.status == InvestigationStatus.COMPLETED
    assert "DP increased" in completed.conclusion
