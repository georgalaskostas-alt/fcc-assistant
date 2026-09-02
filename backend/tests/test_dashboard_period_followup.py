from app.dashboard_api import _period_followup_plan
from app.site_model import ProcessUnit


def _widgets():
    return [
        {"id":"hcu-live","type":"kpi","unit_key":"hcu","period":"live"},
        {"id":"hcu-feed-trend","type":"trend","unit_key":"hcu","period":"16h"},
        {"id":"fcc-live","type":"kpi","unit_key":"fcc","period":"live"},
        {"id":"fcc-feed-trend","type":"trend","unit_key":"fcc","period":"16h"},
    ]


def test_elliptical_plural_followup_updates_both_existing_trends():
    result=_period_followup_plan("Τελικά τα θέλω 8 ώρες.",{"last_action":"transaction"},_widgets(),[])
    assert result is not None
    plan,message=result
    assert plan["action"]=="update_widgets"
    assert plan["period"]=="8h"
    assert set(plan["target_ids"])=={"hcu-feed-trend","fcc-feed-trend"}
    assert "2" in message


def test_period_followup_does_not_guess_without_context():
    assert _period_followup_plan("8 ώρες",{},_widgets(),[]) is None


def test_explicit_unit_limits_period_update_to_that_unit():
    hcu=ProcessUnit("hcu","HCU",(),())
    result=_period_followup_plan("Το διάγραμμα στο HCU να γίνει 8h",{},_widgets(),[hcu])
    assert result is not None
    plan,_=result
    assert plan["target_ids"]==["hcu-feed-trend"]
