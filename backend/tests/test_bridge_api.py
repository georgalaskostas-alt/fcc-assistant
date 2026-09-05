from app.bridge_api import bridge_capabilities, bridge_site_catalog


def test_bridge_capabilities_are_local_read_only():
    payload = bridge_capabilities()
    assert payload["mode"] == "local"
    assert payload["read_only"] is True
    assert payload["external_ai"] is False
    assert payload["plant_write_access"] is False
    assert payload["transport"]["scope"] == "loopback"


def test_bridge_site_catalog_contains_fcc_metadata():
    payload = bridge_site_catalog()
    assert payload["read_only"] is True
    fcc = next(unit for unit in payload["units"] if unit["key"] == "fcc")
    assert any(tag["key"] == "feed_flow" for tag in fcc["tags"])
