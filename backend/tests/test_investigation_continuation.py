import pytest
from backend.app.investigation_continuation import continue_saved_investigation
from backend.app.investigation_store import InvestigationStore
from backend.app.agent_tools import ToolContext,ToolRegistry
from backend.app.refinery_model import AccessGrant,DataDomain,RefineryScope,ScopeKind,UnitScope

def _context(actor="eng",unit="fcc"):
    refinery=RefineryScope(key="site",name="Site",units=(UnitScope(key="fcc",name="FCC"),UnitScope(key="hcu",name="HCU")))
    access=AccessGrant(actor_id=actor,allowed_domains=frozenset({DataDomain.PROCESS,DataDomain.KNOWLEDGE}),refinery_keys=frozenset({"site"}),unit_keys=frozenset({unit}))
    return ToolContext(actor_id=actor,refinery=refinery,access=access,scope_kind=ScopeKind.UNIT,scope_id=unit)

@pytest.mark.asyncio
async def test_continuation_rejects_other_user(tmp_path):
    store=InvestigationStore(tmp_path/"i.json")
    inv=store.create(goal="Regenerator DP",user_id="other",unit_key="fcc")
    with pytest.raises(PermissionError):
        await continue_saved_investigation(registry=ToolRegistry(),store=store,investigation_id=inv.id,
            context=_context(),data_source={"data_quality":"SIMULATED"})

@pytest.mark.asyncio
async def test_continuation_rejects_cross_unit_scope(tmp_path):
    store=InvestigationStore(tmp_path/"i.json")
    inv=store.create(goal="Regenerator DP",user_id="eng",unit_key="hcu")
    with pytest.raises(PermissionError):
        await continue_saved_investigation(registry=ToolRegistry(),store=store,investigation_id=inv.id,
            context=_context(unit="fcc"),data_source={"data_quality":"SIMULATED"})
