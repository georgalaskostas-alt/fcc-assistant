from app.dashboard_agent import _compile_operation
from app.site_model import default_site_model


def test_one_metric_across_all_units_expands_to_one_widget_per_unit():
    site = default_site_model()
    operation = {
        "action": "add",
        "units": [],
        "metrics": ["feed flow"],
        "scope": "all_units",
        "widget_type": "trend",
        "period": "16h",
        "missing": [],
    }
    plans, pending, error = _compile_operation(operation, site, {}, [])
    assert error is None
    assert pending is None
    assert len(plans) == 2
    assert {plan["widget"]["unit_key"] for plan in plans} == {"fcc", "hcu"}
    assert all(plan["widget"]["period"] == "16h" for plan in plans)
    assert all(plan["widget"]["type"] == "trend" for plan in plans)


def test_missing_units_keeps_metric_in_pending_frame():
    site = default_site_model()
    operation = {
        "action": "add",
        "units": [],
        "metrics": ["feed flow"],
        "scope": "explicit",
        "widget_type": "trend",
        "period": "16h",
        "missing": [],
    }
    plans, pending, error = _compile_operation(operation, site, {}, [])
    assert plans == []
    assert error == "Σε ποια μονάδα ή μονάδες το θέλεις;"
    assert pending is not None
    assert pending["metrics"] == ["feed flow"]
    assert pending["period"] == "16h"
    assert "units" in pending["missing"]


def test_completed_followup_units_execute_preserved_metric_and_period():
    site = default_site_model()
    completed = {
        "action": "add",
        "units": ["hcu", "fcc"],
        "metrics": ["feed flow"],
        "scope": "explicit",
        "widget_type": "trend",
        "period": "16h",
        "missing": [],
    }
    plans, pending, error = _compile_operation(completed, site, {}, [])
    assert error is None
    assert pending is None
    assert len(plans) == 2
    assert {plan["widget"]["unit_key"] for plan in plans} == {"fcc", "hcu"}
    assert {tuple(plan["widget"]["tag_keys"]) for plan in plans} == {("feed_flow",), ("hcu_feed_flow",)}
