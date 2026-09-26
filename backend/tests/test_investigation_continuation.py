import pytest
from backend.app.investigation_continuation import continue_saved_investigation
from backend.app.investigation_store import InvestigationStore
from backend.app.agent_tools import ToolContext,ToolRegistry
from backend.app.refinery_model import AccessGrant,DataDomain,RefineryScope,ScopeKind,UnitScope

def _context(actor="eng",unit="fcc"):
    refinery=RefineryScope(id="site",name="Site",standalone_units=(UnitScope(id="fcc",name="FCC"),UnitScope(id="hcu",name="HCU")))
    access=AccessGrant(domains=frozenset({DataDomain.PROCESS,DataDomain.KNOWLEDGE}),unit_ids=frozenset({unit}))
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


@pytest.mark.asyncio
async def test_continuation_persists_new_evidence_for_next_resume(tmp_path, monkeypatch):
    from backend.app import investigation_continuation

    store=InvestigationStore(tmp_path/"i.json")
    inv=store.create(goal="Regenerator DP",user_id="eng",unit_key="fcc")
    store.save_checkpoint(inv.id,trail={},resume_context={
        "unit_key":"fcc",
        "time_window":{"start":"2026-09-24T00:00:00Z","end":"2026-09-25T00:00:00Z"},
        "resolved_tags":["regenerator_dp"],
        "autonomous_rounds_completed":0,
    })

    async def fake_loop(**kwargs):
        synthesis=kwargs["synthesis"]
        synthesis["evidence_package"].append({
            "stable_evidence_id":"history:regenerator_dp:a:b",
            "evidence_id":"get_history:follow-up-0",
            "tool":"get_history",
            "description":"New resumed historian evidence",
            "data":{"tag_key":"regenerator_dp","values":[{"value":0.9}]},
            "provenance":{"source":"test"},
        })
        synthesis["resolved_tags"]=["regenerator_dp"]
        return {"rounds_completed":1,"stop_reason":"no_new_evidence","rounds":[]}

    async def fake_reasoning(**kwargs):
        return {"text":"test","investigation_trail":{}}

    monkeypatch.setattr(investigation_continuation,"run_autonomous_evidence_loop",fake_loop)
    monkeypatch.setattr(investigation_continuation,"reason_about_investigation",fake_reasoning)

    await continue_saved_investigation(
        registry=ToolRegistry(),store=store,investigation_id=inv.id,
        context=_context(),data_source={"data_quality":"SIMULATED"},
    )

    persisted=store.get(inv.id)
    assert persisted is not None
    assert len(persisted.evidence)==1
    assert persisted.evidence[0].source_id=="history:regenerator_dp:a:b"
    assert persisted.resume_context["evidence_count"]==1

    # A second resume must reconstruct the evidence package from durable state
    # rather than losing what the previous autonomous round discovered.
    seen={}
    async def second_loop(**kwargs):
        seen["ids"]=[item.get("evidence_id") for item in kwargs["synthesis"]["evidence_package"]]
        return {"rounds_completed":0,"stop_reason":"no_new_evidence","rounds":[]}

    monkeypatch.setattr(investigation_continuation,"run_autonomous_evidence_loop",second_loop)
    await continue_saved_investigation(
        registry=ToolRegistry(),store=store,investigation_id=inv.id,
        context=_context(),data_source={"data_quality":"SIMULATED"},
    )
    assert seen["ids"]==["history:regenerator_dp:a:b"]
