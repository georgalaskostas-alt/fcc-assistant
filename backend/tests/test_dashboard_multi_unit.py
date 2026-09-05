from app.dashboard_config import plan_dashboard_command
from app.site_model import ProcessUnit, SiteModel, UnitTag


def test_planner_resolves_requested_unit_in_multi_unit_site():
    site = SiteModel(
        name="Demo",
        units=(
            ProcessUnit("fcc", "FCC", (UnitTag("feed", "FCC Feed", "m3/h", ("τροφοδοσία",)),)),
            ProcessUnit("cdu", "CDU", (UnitTag("feed", "CDU Feed", "m3/h", ("τροφοδοσία",)),)),
        ),
    )

    plan = plan_dashboard_command("βάλε γράφημα τροφοδοσία CDU 8h", site)
    widget = plan["widget"]
    assert widget["unit_key"] == "cdu"
    assert widget["type"] == "trend"
    assert widget["period"] == "8h"
