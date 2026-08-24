from pathlib import Path

from app.dashboard_agent import _compile
from app.dashboard_dialogue import DashboardDialogueStore, contextual_plan
from app.site_model import default_site_model


def _widgets():
    return [
        {"id":"f1","type":"trend","title":"Feed Flow","unit_key":"fcc","tag_keys":["feed_flow"],"period":"8h","layout":{"order":0,"width":12,"height":"tall"}},
        {"id":"f2","type":"trend","title":"Reactor Temperature","unit_key":"fcc","tag_keys":["reactor_temp"],"period":"8h","layout":{"order":1,"width":12,"height":"tall"}},
        {"id":"h1","type":"trend","title":"HCU Feed Flow","unit_key":"hcu","tag_keys":["hcu_feed_flow"],"period":"8h","layout":{"order":2,"width":12,"height":"tall"}},
        {"id":"h2","type":"trend","title":"HCU Reactor Temperature","unit_key":"hcu","tag_keys":["hcu_reactor_temp"],"period":"8h","layout":{"order":3,"width":12,"height":"tall"}},
    ]


def test_remove_all_without_unit_targets_all_trends():
    plan,error=_compile({"action":"remove_all","unit":None},default_site_model(),{},_widgets())
    assert error is None
    assert plan is not None
    assert plan["action"]=="remove_widgets"
    assert set(plan["target_ids"])=={"f1","f2","h1","h2"}


def test_removed_batch_is_persisted_and_restorable(tmp_path: Path):
    dialogue=DashboardDialogueStore(tmp_path/"dialogue.json")
    before=_widgets()
    plan={"action":"remove_widgets","target_ids":[w["id"] for w in before],"read_only":True,"requires_confirmation":False}
    dialogue.remember("ops","Αφαίρεσε όλα τα διαγράμματα από παντού",plan,{"widgets":[]},"Τα αφαίρεσα.",previous_widgets=before)
    state=dialogue.get_state("ops")
    assert len(state["last_removed_widgets"])==4
    restored,message=contextual_plan("βάλε τα πάλι πίσω αυτά που αφαίρεσες",default_site_model(),state,[])
    assert restored is not None
    assert restored["action"]=="add_widgets"
    assert {w["id"] for w in restored["widgets"]}=={"f1","f2","h1","h2"}
    assert "Επανέφερα" in (message or "")


def test_agent_restore_uses_exact_snapshot_not_reconstructed_metrics():
    state={"last_removed_widgets":_widgets()}
    plan,error=_compile({"action":"restore","reference":"removed_batch"},default_site_model(),state,[])
    assert error is None
    assert plan is not None
    assert plan["action"]=="add_widgets"
    assert [w["id"] for w in plan["widgets"]]==["f1","f2","h1","h2"]
