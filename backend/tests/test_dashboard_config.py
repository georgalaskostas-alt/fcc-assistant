import pytest

from app.dashboard_config import DashboardCommandError, plan_dashboard_command
from app.site_model import ProcessUnit, SiteModel, UnitTag, default_site_model


def test_greek_trend_command_resolves_fcc_feed():
    plan = plan_dashboard_command("Θέλω γράφημα με την τροφοδοσία για 8h", default_site_model())
    assert plan["action"] == "add_widget"
    assert plan["widget"]["type"] == "trend"
    assert plan["widget"]["unit_key"] == "fcc"
    assert plan["widget"]["tag_keys"] == ("feed_flow",)
    assert plan["widget"]["period"] == "8h"
    assert plan["read_only"] is True


def test_average_command_resolves_alias():
    plan = plan_dashboard_command("βάλε μέσο όρο O2", default_site_model())
    assert plan["widget"]["type"] == "average"
    assert plan["widget"]["tag_keys"] == ("regenerator_o2",)


def test_summary_does_not_require_tag():
    plan = plan_dashboard_command("Θέλω σύνοψη της FCC", default_site_model())
    assert plan["widget"]["type"] == "summary"
    assert plan["widget"]["tag_keys"] == ()


def test_multi_unit_requires_resolved_unit():
    site = SiteModel(
        "Refinery",
        (
            ProcessUnit("fcc", "FCC", (UnitTag("feed", "Feed", "m3/h"),)),
            ProcessUnit("cdu", "CDU", (UnitTag("feed", "Feed", "m3/h"),)),
        ),
    )
    with pytest.raises(DashboardCommandError):
        plan_dashboard_command("βάλε γράφημα feed", site)
