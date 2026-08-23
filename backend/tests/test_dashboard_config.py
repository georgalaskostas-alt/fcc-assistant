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
    assert plan["widget"]["layout"] == {"order": 0, "width": 12, "height": "tall"}
    assert plan["read_only"] is True


def test_average_command_resolves_alias():
    plan = plan_dashboard_command("βάλε μέσο όρο O2", default_site_model())
    assert plan["widget"]["type"] == "average"
    assert plan["widget"]["tag_keys"] == ("regenerator_o2",)
    assert plan["widget"]["layout"]["width"] == 4


def test_summary_does_not_require_tag():
    plan = plan_dashboard_command("Θέλω σύνοψη της FCC", default_site_model())
    assert plan["widget"]["type"] == "summary"
    assert plan["widget"]["tag_keys"] == ()


def test_move_summary_between_feed_kpi_and_reactor_chart():
    widgets = [
        {"id": "fcc-kpi-feed_flow", "type": "kpi", "title": "Feed Flow", "unit_key": "fcc", "tag_keys": ["feed_flow"]},
        {"id": "fcc-trend-reactor_temp", "type": "trend", "title": "Reactor Temperature", "unit_key": "fcc", "tag_keys": ["reactor_temp"]},
        {"id": "fcc-summary-summary", "type": "summary", "title": "FCC Summary", "unit_key": "fcc", "tag_keys": []},
    ]
    plan = plan_dashboard_command(
        "Χώρεσε τη σύνοψη ανάμεσα στην τιμή της τροφοδοσίας και το γράφημα reactor temperature",
        default_site_model(),
        current_widgets=widgets,
    )
    assert plan["action"] == "move_between"
    assert plan["target_id"] == "fcc-summary-summary"
    assert plan["first_id"] == "fcc-kpi-feed_flow"
    assert plan["second_id"] == "fcc-trend-reactor_temp"


def test_remove_fcc_feed_chart_is_unit_aware():
    widgets = [
        {"id": "fcc-trend-feed_flow", "type": "trend", "title": "Feed Flow", "unit_key": "fcc", "tag_keys": ["feed_flow"]},
        {"id": "hcu-trend-feed_flow", "type": "trend", "title": "Feed Flow", "unit_key": "hcu", "tag_keys": ["feed_flow"]},
    ]
    plan = plan_dashboard_command(
        "Αφαίρεσε το γράφημα τροφοδοσίας από το FCC",
        default_site_model(),
        current_widgets=widgets,
    )
    assert plan["action"] == "remove_widget"
    assert plan["target_id"] == "fcc-trend-feed_flow"


def test_remove_the_fcc_chart_without_tag_when_only_one_exists():
    widgets = [
        {"id": "fcc-trend-feed_flow", "type": "trend", "title": "Feed Flow", "unit_key": "fcc", "tag_keys": ["feed_flow"]},
        {"id": "fcc-kpi-feed_flow", "type": "kpi", "title": "Feed Flow", "unit_key": "fcc", "tag_keys": ["feed_flow"]},
        {"id": "hcu-trend-feed_flow", "type": "trend", "title": "Feed Flow", "unit_key": "hcu", "tag_keys": ["feed_flow"]},
    ]
    plan = plan_dashboard_command("Αφαίρεσε το γράφημα του FCC", default_site_model(), current_widgets=widgets)
    assert plan["action"] == "remove_widget"
    assert plan["target_id"] == "fcc-trend-feed_flow"


def test_generic_fcc_chart_removal_asks_for_clarification_when_ambiguous():
    widgets = [
        {"id": "fcc-trend-feed_flow", "type": "trend", "title": "Feed Flow", "unit_key": "fcc", "tag_keys": ["feed_flow"]},
        {"id": "fcc-trend-reactor_temp", "type": "trend", "title": "Reactor Temperature", "unit_key": "fcc", "tag_keys": ["reactor_temp"]},
    ]
    with pytest.raises(DashboardCommandError, match="Πες μου ποιο"):
        plan_dashboard_command("Αφαίρεσε το γράφημα του FCC", default_site_model(), current_widgets=widgets)


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
