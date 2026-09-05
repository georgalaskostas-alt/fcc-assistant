from app.dashboard_agent import _compile_operation, _operation_from_legacy, _simulate
from app.dashboard_store import DashboardStore
from app.site_model import ProcessUnit, SiteModel, UnitTag

def site():
    return SiteModel("Test Refinery",(ProcessUnit("fcc","FCC",(UnitTag("fcc_reactor","Reactor Temperature","C",("reaction temperature",),"reaction_temperature"),UnitTag("fcc_feed","Feed Flow","m3/h",("feed",),"feed_flow")),("fluid catalytic cracking",)),ProcessUnit("hcu","Hydrocracker",(UnitTag("hcu_reactor","HCU Reactor Temperature","C",("reaction temperature",),"reaction_temperature"),UnitTag("hcu_feed","HCU Feed Flow","m3/h",("feed",),"feed_flow")),("hydrocracker","hydro cracking","hcu"))))
def _compile(intent,s,state,working):
    operation=_operation_from_legacy(intent);plans,pending,error=_compile_operation(operation,s,state,working)
    if error:return None,error
    if pending is not None:return None,"Ποιο ακριβώς γράφημα εννοείς;" if "reference" in (pending.get("missing") or []) else "Χρειάζομαι μία ακόμη πληροφορία."
    if not plans:return None,None
    return (plans[0] if len(plans)==1 else {"action":"transaction","steps":plans,"read_only":True,"requires_confirmation":False}),None
def test_two_adds_stay_in_explicit_hydrocracker():
    s=site();working=[];plans=[]
    for intent in [{"action":"add","unit":"hydrocracker","metric":"reaction temperature","widget_type":"trend"},{"action":"add","unit":"hydrocracker","metric":"feed","widget_type":"trend"}]:
        plan,error=_compile(intent,s,{},working);assert error is None and plan is not None;plans.append(plan);working=_simulate(working,plan)
    assert [p["widget"]["unit_key"] for p in plans]==["hcu","hcu"]
def test_move_last_fcc_reactor_to_hcu_preserves_semantic():
    s=site();widgets=[{"id":"w1","type":"trend","title":"Reactor Temperature","unit_key":"fcc","tag_keys":["fcc_reactor"],"period":"8h","layout":{"order":0,"width":12,"height":"tall"}}];plan,error=_compile({"action":"move","unit":"hydrocracker","reference":"last"},s,{"last_widget":{"id":"w1"}},widgets);assert error is None and plan["widget"]["unit_key"]=="hcu" and plan["widget"]["tag_keys"]==["hcu_reactor"]
def test_remove_all_hcu_does_not_touch_fcc():
    s=site();widgets=[{"id":"f1","type":"trend","unit_key":"fcc","tag_keys":["fcc_feed"]},{"id":"h1","type":"trend","unit_key":"hcu","tag_keys":["hcu_feed"]},{"id":"h2","type":"trend","unit_key":"hcu","tag_keys":["hcu_reactor"]}];plan,error=_compile({"action":"remove_all","unit":"hydrocracker"},s,{},widgets);assert error is None and set(plan["target_ids"])=={"h1","h2"}
def test_ambiguous_remove_refuses_to_guess():
    s=site();widgets=[{"id":"a","type":"trend","title":"Feed Flow","unit_key":"fcc","tag_keys":["fcc_feed"]},{"id":"b","type":"trend","title":"Feed Flow backup","unit_key":"fcc","tag_keys":["fcc_feed"]}];plan,error=_compile({"action":"remove","unit":"fcc","metric":"feed"},s,{},widgets);assert plan is None and error=="Ποιο ακριβώς γράφημα εννοείς;"
def test_update_period_all_existing_feed_trends_preserves_ids():
    s=site();widgets=[{"id":"f1","type":"trend","title":"Feed Flow","unit_key":"fcc","tag_keys":["fcc_feed"],"period":"16h"},{"id":"h1","type":"trend","title":"HCU Feed Flow","unit_key":"hcu","tag_keys":["hcu_feed"],"period":"16h"},{"id":"k1","type":"kpi","unit_key":"fcc","tag_keys":["fcc_feed"],"period":"16h"}]
    op={"action":"update","units":["fcc","hcu"],"metrics":["feed_flow"],"scope":"all_units","reference":"all","period":"8h"};plans,pending,error=_compile_operation(op,s,{},widgets);assert error is None and pending is None and len(plans)==1;plan=plans[0];assert plan["action"]=="update_widgets" and set(plan["target_ids"])=={"f1","h1"};updated=_simulate(widgets,plan);assert [(w["id"],w.get("period")) for w in updated]==[("f1","8h"),("h1","8h"),("k1","16h")]
def test_store_update_period_is_in_place(tmp_path):
    store=DashboardStore(tmp_path/"dashboards.json");store.put("ops",{"title":"Ops","widgets":[{"id":"f1","type":"trend","unit_key":"fcc","tag_keys":["fcc_feed"],"period":"16h"},{"id":"h1","type":"trend","unit_key":"hcu","tag_keys":["hcu_feed"],"period":"16h"}]});result=store.apply_plan("ops",{"action":"update_widgets","target_ids":["f1","h1"],"period":"8h"});assert [w["id"] for w in result["widgets"]]==["f1","h1"] and [w["period"] for w in result["widgets"]]==["8h","8h"]
def test_transaction_is_single_final_write(tmp_path):
    store=DashboardStore(tmp_path/"dashboards.json");store.put("ops",{"title":"Ops","widgets":[]});steps=[{"action":"add_widget","widget":{"id":"f1","type":"trend","unit_key":"fcc","tag_keys":["fcc_feed"]}},{"action":"add_widget","widget":{"id":"h1","type":"trend","unit_key":"hcu","tag_keys":["hcu_feed"]}},{"action":"remove_widget","target_id":"f1"}];result=store.apply_transaction("ops",steps);assert [w["id"] for w in result["widgets"]]==["h1"]
