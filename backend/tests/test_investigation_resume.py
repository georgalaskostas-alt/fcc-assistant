from backend.app.investigation_store import InvestigationStore, InvestigationStatus
from backend.app.investigation_service import InvestigationService
from backend.app.agent_tools import ToolRegistry

def test_checkpoint_survives_store_reload_and_can_resume(tmp_path):
    path=tmp_path/"investigations.json"
    store=InvestigationStore(path)
    inv=store.create(goal="Why did regenerator DP rise?",user_id="engineer",unit_key="fcc")
    service=InvestigationService(registry=ToolRegistry(),store=store)
    saved=service.checkpoint(inv.id,trail={"stop_reason":"no_new_evidence"},
        synthesis={"unit_key":"fcc","time_window":{"start":"a","end":"b"},"resolved_tags":["dp","o2"],
                   "last_autonomous_focus":"dp-o2","autonomous_rounds_completed":2,"evidence_count":7})
    assert saved.status == InvestigationStatus.WAITING
    reloaded=InvestigationStore(path)
    item=reloaded.get(inv.id)
    assert item is not None
    assert item.trail["stop_reason"] == "no_new_evidence"
    resumed=InvestigationService(registry=ToolRegistry(),store=reloaded).resume_context(inv.id)
    assert resumed["goal"] == "Why did regenerator DP rise?"
    assert resumed["resume_context"]["resolved_tags"] == ["dp","o2"]
    assert reloaded.get(inv.id).status == InvestigationStatus.RUNNING
