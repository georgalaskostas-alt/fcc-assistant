from backend.app.investigation_store import InvestigationStore
from backend.app.investigation_service import InvestigationService
from backend.app.agent_tools import ToolRegistry

def test_conversation_resolves_saved_investigation_by_topic(tmp_path):
    store=InvestigationStore(tmp_path/"i.json")
    target=store.create(goal="Why did regenerator DP rise yesterday?",user_id="eng",unit_key="fcc")
    store.save_checkpoint(target.id,trail={"x":1},resume_context={"last_autonomous_focus":"regenerator dp oxygen"})
    store.create(goal="Wet gas compressor vibration",user_id="eng",unit_key="fcc")
    service=InvestigationService(registry=ToolRegistry(),store=store)
    result=service.resolve_and_resume(user_id="eng",utterance="συνέχισε εκείνο το θέμα με το regenerator",unit_key="fcc")
    assert result["status"]=="resolved"
    assert result["resume"]["investigation_id"]==target.id

def test_conversation_never_crosses_user_boundary(tmp_path):
    store=InvestigationStore(tmp_path/"i.json")
    other=store.create(goal="Regenerator DP investigation",user_id="other",unit_key="fcc")
    store.save_checkpoint(other.id,trail={},resume_context={"last_autonomous_focus":"regenerator dp"})
    result=InvestigationService(registry=ToolRegistry(),store=store).resolve_and_resume(
        user_id="eng",utterance="continue regenerator investigation",unit_key="fcc")
    assert result["status"]=="not_found"
