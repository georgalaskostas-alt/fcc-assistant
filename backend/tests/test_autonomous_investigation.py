from datetime import datetime, timezone

import pytest

from app.agent_tools import ToolContext, ToolDefinition, ToolEffect, ToolParameter, ToolRegistry
from app.autonomous_investigation import AutonomousInvestigator
from app.investigation_planner import InvestigationPlanner
from app.investigation_store import InvestigationStore
from app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope


def _context():
    refinery = RefineryScope(id="site", name="Site", standalone_units=(UnitScope(id="fcc", name="FCC"),))
    grant = AccessGrant(
        domains=frozenset({DataDomain.PROCESS, DataDomain.KNOWLEDGE}),
        refinery_ids=frozenset({"site"}),
    )
    return ToolContext(actor_id="engineer-1", refinery=refinery, access=grant, scope_kind=ScopeKind.UNIT, scope_id="fcc")


@pytest.mark.asyncio
async def test_goal_becomes_governed_persistent_investigation(tmp_path):
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="search_tags", description="tags", domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY, parameters=(ToolParameter("query", "string"),),
        ),
        lambda _ctx, _args: [{"key": "regenerator_dp", "name": "Regenerator DP"}],
    )
    registry.register(
        ToolDefinition(
            name="search_archive", description="archive", domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.READ_ONLY,
            parameters=(
                ToolParameter("query", "string"), ToolParameter("unit_key", "string"),
                ToolParameter("approved_only", "boolean", required=False),
                ToolParameter("limit", "integer", required=False),
            ),
        ),
        lambda _ctx, _args: [{"document_id": "FCC-OM-1", "revision": "4", "page": 21}],
    )
    planner = InvestigationPlanner(now_provider=lambda: datetime(2026, 9, 15, 12, tzinfo=timezone.utc))
    store = InvestigationStore(tmp_path / "investigations.json")
    investigator = AutonomousInvestigator(registry=registry, store=store, planner=planner)

    result = await investigator.investigate(
        goal="Γιατί ανέβηκε το ΔP του regenerator χθες;",
        user_id="engineer-1",
        unit_key="fcc",
        context=_context(),
    )

    assert result.investigation_id
    assert result.synthesis.ready_for_reasoning is True
    assert result.synthesis.evidence_count == 2
    persisted = store.get(result.investigation_id)
    assert persisted is not None
    assert persisted.goal.startswith("Γιατί")
    assert len(persisted.evidence) == 2


def test_planner_resolves_yesterday_window():
    planner = InvestigationPlanner(now_provider=lambda: datetime(2026, 9, 15, 12, tzinfo=timezone.utc))
    intent = planner.understand("Γιατί ανέβηκε το ΔP χθες;", unit_key="FCC")
    assert intent.unit_key == "fcc"
    assert intent.period_interpretation == "previous_local_calendar_day"\n    assert intent.start_time.startswith("2026-09-13T21:00:00")\n    assert intent.end_time.startswith("2026-09-14T21:00:00")
