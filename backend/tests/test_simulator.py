from datetime import datetime, timezone

from app.simulator import SimulatedFCCSource


def test_simulator_generates_shift_data() -> None:
    source = SimulatedFCCSource()
    start = datetime(2026, 8, 19, 7, tzinfo=timezone.utc)
    end = datetime(2026, 8, 19, 15, tzinfo=timezone.utc)
    data = source.recorded_values("regen_temp", start, end)
    assert len(data["Items"]) == 33
    assert data["Items"][-1]["Value"] > data["Items"][0]["Value"]


def test_simulator_has_expected_demo_tags() -> None:
    keys = {item["key"] for item in SimulatedFCCSource().list_tags()}
    assert {"feed_flow", "reactor_temp", "regen_temp", "regen_o2", "lcco_rate"}.issubset(keys)
