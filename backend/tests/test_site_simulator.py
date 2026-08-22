from app.simulator import SimulatedSiteSource
from app.site_model import ProcessUnit, SiteModel, UnitTag


def test_site_simulator_generates_data_for_multiple_units():
    site = SiteModel(
        "Refinery",
        (
            ProcessUnit("fcc", "FCC", (UnitTag("fcc_feed", "FCC Feed", "m3/h", (), "feed_flow"),)),
            ProcessUnit("hcu", "Hydrocracker", (UnitTag("hcu_feed", "HCU Feed", "m3/h", (), "feed_flow"),)),
        ),
    )

    source = SimulatedSiteSource(site)
    tags = source.list_tags()
    data = source.demo_shift()

    assert {item["key"] for item in tags} == {"fcc_feed", "hcu_feed"}
    assert {item["unit_key"] for item in tags} == {"fcc", "hcu"}
    assert set(data) == {"fcc_feed", "hcu_feed"}
    assert len(data["fcc_feed"]["Items"]) == 33
    assert len(data["hcu_feed"]["Items"]) == 33
    assert data["fcc_feed"]["Items"][0]["Value"] != data["hcu_feed"]["Items"][0]["Value"]


def test_site_simulator_rejects_duplicate_global_tag_keys():
    site = SiteModel(
        "Refinery",
        (
            ProcessUnit("fcc", "FCC", (UnitTag("feed", "FCC Feed", "m3/h", (), "feed_flow"),)),
            ProcessUnit("hcu", "Hydrocracker", (UnitTag("feed", "HCU Feed", "m3/h", (), "feed_flow"),)),
        ),
    )

    try:
        SimulatedSiteSource(site)
    except ValueError as exc:
        assert "globally unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate site tag keys to be rejected")
