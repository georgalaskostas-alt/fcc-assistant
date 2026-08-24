from app.dashboard_agent import _compile, _simulate
from app.dashboard_store import DashboardStore
from app.site_model import ProcessUnit, SiteModel, UnitTag


def site():
    return SiteModel("Test Refinery", (
        ProcessUnit("fcc", "FCC", (
            UnitTag("fcc_reactor", "Reactor Temperature", "C", ("reaction temperature",), "reaction_temperature"),
            UnitTag("fcc_feed", "Feed Flow", "m3/h", ("feed",), "feed_flow"),
        ), ("fluid catalytic cracking",)),
        ProcessUnit("hcu", "Hydrocracker", (
            UnitTag("hcu_reactor", "HCU Reactor Temperature", "C", ("reaction temperature",), "reaction_temperature"),
            UnitTag("hcu_feed", "HCU Feed Flow", "m3/h", ("feed",), "feed_flow"),
        ), ("hydrocracker", "hydro cracking", "hcu")),
    ))


def test_two_adds_stay_in_explicit_hydrocracker():
    s=site(); state={}; working=[]; plans=[]
    for intent in [
        {"action":"add","unit":"hydrocracker","metric":"reaction temperature","widget_type":"trend"},
        {"action":"add","unit":"hydrocracker","metric":"feed","widget_type":"trend"},
    ]:
        plan,error=_compile(intent,s,state,working)
        assert error is None and plan is not None
        plans.append(plan); working=_simulate(working,plan)
    assert [p["widget"]["unit_key"] for p in plans]==["hcu","hcu"]
    assert [p["widget"]["tag_keys"][0] for p in plans]==["hcu_reactor","hcu_feed"]


def test_move_last_fcc_reactor_to_hcu_preserves_semantic():
    s=site(); widgets=[{"id":"w1","type":"trend","title":"Reactor Temperature","unit_key":"fcc","tag_keys":["fcc_reactor"],"period":"8h","layout":{"order":0,"width":12,"height":"tall"}}]
    plan,error=_compile({"action":"move","unit":"hydrocracker","reference":"last"},s,{"last_widget":{"id":"w1"}},widgets)
    assert error is None and plan is not None
    assert plan["action"]=="replace_widget"
    assert plan["target_id"]=="w1"
    assert plan["widget"]["unit_key"]=="hcu"
    assert plan["widget"]["tag_keys"]==["hcu_reactor"]


def test_remove_all_hcu_does_not_touch_fcc():
    s=site(); widgets=[
        {"id":"f1","type":"trend","unit_key":"fcc","tag_keys":["fcc_feed"]},
        {"id":"h1","type":"trend","unit_key":"hcu","tag_keys":["hcu_feed"]},
        {"id":"h2","type":"trend","unit_key":"hcu","tag_keys":["hcu_reactor"]},
    ]
    plan,error=_compile({"action":"remove_all","unit":"hydrocracker"},s,{},widgets)
    assert error is None and plan is not None
    assert set(plan["target_ids"])=={"h1","h2"}
    remaining=_simulate(widgets,plan)
    assert [w["id"] for w in remaining]==["f1"]


def test_ambiguous_remove_refuses_to_guess():
    s=site(); widgets=[
        {"id":"a","type":"trend","title":"Feed Flow","unit_key":"fcc","tag_keys":["fcc_feed"]},
        {"id":"b","type":"trend","title":"Feed Flow backup","unit_key":"fcc","tag_keys":["fcc_feed"]},
    ]
    plan,error=_compile({"action":"remove","unit":"fcc","metric":"feed"},s,{},widgets)
    assert plan is None
    assert error=="Ποιο ακριβώς γράφημα εννοείς;"


def test_transaction_is_single_final_write(tmp_path):
    store=DashboardStore(tmp_path/"dashboards.json")
    store.put("ops",{"title":"Ops","widgets":[]})
    steps=[
        {"action":"add_widget","widget":{"id":"f1","type":"trend","unit_key":"fcc","tag_keys":["fcc_feed"]}},
        {"action":"add_widget","widget":{"id":"h1","type":"trend","unit_key":"hcu","tag_keys":["hcu_feed"]}},
        {"action":"remove_widget","target_id":"f1"},
    ]
    result=store.apply_transaction("ops",steps)
    assert [w["id"] for w in result["widgets"]]==["h1"]
    persisted=store.get("ops")
    assert [w["id"] for w in persisted["widgets"]]==["h1"]
