from app.dashboard_api import _period_followup_plan
from app.site_model import ProcessUnit


def _widgets():
    return [
        {"id":"hcu-live","type":"kpi","unit_key":"hcu","period":"live","title":"Feed Flow","tag_keys":["hcu_feed"]},
        {"id":"hcu-feed-trend","type":"trend","unit_key":"hcu","period":"16h","title":"Feed Flow","tag_keys":["hcu_feed"]},
        {"id":"fcc-live","type":"kpi","unit_key":"fcc","period":"live","title":"Feed Flow","tag_keys":["fcc_feed"]},
        {"id":"fcc-feed-trend","type":"trend","unit_key":"fcc","period":"16h","title":"Feed Flow","tag_keys":["fcc_feed"]},
    ]


def test_elliptical_plural_followup_updates_both_existing_trends():
    result=_period_followup_plan("Τελικά τα θέλω 8 ώρες.",{"last_action":"clarify"},{"last_action":"transaction","last_touched_widget_ids":["hcu-feed-trend","fcc-feed-trend"]},_widgets(),[])
    assert result is not None
    plan,message=result
    assert plan["action"]=="update_widgets"
    assert plan["period"]=="8h"
    assert set(plan["target_ids"])=={"hcu-feed-trend","fcc-feed-trend"}
    assert "2" in message


def test_period_followup_does_not_guess_without_context():
    assert _period_followup_plan("8 ώρες",{}, {}, _widgets(),[]) is None


def test_explicit_unit_limits_period_update_to_that_unit():
    hcu=ProcessUnit("hcu","HCU",(),())
    result=_period_followup_plan("Το διάγραμμα στο HCU να γίνει 8h",{}, {}, _widgets(),[hcu])
    assert result is not None
    plan,_=result
    assert plan["target_ids"]==["hcu-feed-trend"]


def test_explicit_feed_metric_updates_feed_trends_in_both_units_only():
    widgets=_widgets()+[
        {"id":"hcu-reactor","type":"trend","unit_key":"hcu","period":"16h","title":"Reactor Temperature","tag_keys":["hcu_reactor_temp"]},
        {"id":"fcc-reactor","type":"trend","unit_key":"fcc","period":"16h","title":"Reactor Temperature","tag_keys":["fcc_reactor_temp"]},
    ]
    result=_period_followup_plan("Κάνε τα feed flow και στις δύο μονάδες 8 ώρες",{}, {}, widgets,[])
    assert result is not None
    plan,_=result
    assert set(plan["target_ids"])=={"hcu-feed-trend","fcc-feed-trend"}


def test_live_kpis_are_never_period_updated():
    result=_period_followup_plan("Τα διαγραμματα να γίνουν 8 ώρες",{}, {}, _widgets(),[])
    assert result is not None
    plan,_=result
    assert "hcu-live" not in plan["target_ids"]
    assert "fcc-live" not in plan["target_ids"]
