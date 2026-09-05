from app.dashboard_config import plan_dashboard_command
from app.dashboard_store import DashboardStore
from app.site_model import ProcessUnit, SiteModel, UnitTag


def multi_unit_site() -> SiteModel:
    return SiteModel(
        "Refinery",
        (
            ProcessUnit(
                "fcc",
                "FCC",
                (
                    UnitTag("fcc_feed", "FCC Feed", "m3/h", ("feed", "τροφοδοσία", "τροφοδοσια"), "feed_flow"),
                    UnitTag("fcc_rx", "FCC Reactor Temperature", "C", ("αντίδραση", "αντιδραση", "reactor temperature"), "reaction_temperature"),
                ),
            ),
            ProcessUnit(
                "hcu",
                "Hydrocracker",
                (
                    UnitTag("hcu_feed", "HCU Feed", "m3/h", ("feed", "τροφοδοσία", "τροφοδοσια"), "feed_flow"),
                    UnitTag("hcu_rx", "HCU Reactor Temperature", "C", ("αντίδραση", "αντιδραση", "reactor temperature"), "reaction_temperature"),
                ),
            ),
        ),
    )


def test_one_command_can_create_matching_kpis_for_two_units():
    plan = plan_dashboard_command(
        "Βάλε τροφοδοσία και αντίδραση για FCC και Hydrocracker",
        multi_unit_site(),
    )

    assert plan["action"] == "add_widgets"
    widgets = plan["widgets"]
    assert len(widgets) == 4
    assert {widget["unit_key"] for widget in widgets} == {"fcc", "hcu"}
    assert {tuple(widget["tag_keys"]) for widget in widgets} == {
        ("fcc_feed",),
        ("fcc_rx",),
        ("hcu_feed",),
        ("hcu_rx",),
    }
    assert plan["read_only"] is True


def test_clone_command_maps_semantics_not_pi_tag_names():
    current = [
        {
            "id": "fcc-kpi-fcc_feed",
            "type": "kpi",
            "title": "FCC Feed",
            "unit_key": "fcc",
            "tag_keys": ["fcc_feed"],
            "period": "8h",
            "layout": {"order": 0, "width": 4, "height": "compact"},
        },
        {
            "id": "fcc-trend-fcc_rx",
            "type": "trend",
            "title": "FCC Reactor Temperature",
            "unit_key": "fcc",
            "tag_keys": ["fcc_rx"],
            "period": "8h",
            "layout": {"order": 1, "width": 8, "height": "tall"},
        },
    ]

    plan = plan_dashboard_command(
        "Βάλε τα ίδια του FCC και στο Hydrocracker",
        multi_unit_site(),
        current_widgets=current,
    )

    assert plan["action"] == "add_widgets"
    widgets = plan["widgets"]
    assert len(widgets) == 2
    assert all(widget["unit_key"] == "hcu" for widget in widgets)
    assert {tuple(widget["tag_keys"]) for widget in widgets} == {("hcu_feed",), ("hcu_rx",)}
    assert {widget["layout"]["width"] for widget in widgets} == {4, 8}


def test_store_applies_multi_widget_plan_atomically(tmp_path):
    store = DashboardStore(tmp_path / "dashboards.json")
    plan = plan_dashboard_command(
        "Βάλε τροφοδοσία και αντίδραση για FCC και Hydrocracker",
        multi_unit_site(),
    )

    result = store.apply_plan("supervisor", plan)
    assert result["workspace"] == "supervisor"
    assert len(result["widgets"]) == 4
    assert [widget["layout"]["order"] for widget in result["widgets"]] == [0, 1, 2, 3]
