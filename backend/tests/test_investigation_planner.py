from datetime import datetime, timezone

from backend.app.investigation_planner import InvestigationPlanner


def test_yesterday_means_previous_calendar_day_in_site_timezone():
    planner = InvestigationPlanner(
        now_provider=lambda: datetime(2026, 9, 17, 13, 20, tzinfo=timezone.utc),
        site_timezone="Europe/Athens",
    )
    intent = planner.understand("Γιατί ανέβηκε το ΔP του regenerator χθες;", unit_key="fcc")
    assert intent.period_interpretation == "previous_local_calendar_day"
    assert intent.site_timezone == "Europe/Athens"
    # September Athens is UTC+3: local 2026-09-16 00:00 -> UTC 2026-09-15 21:00.
    assert intent.start_time == "2026-09-15T21:00:00+00:00"
    assert intent.end_time == "2026-09-16T21:00:00+00:00"


def test_greek_diacritic_normalization_keeps_yesterday_detection():
    planner = InvestigationPlanner(
        now_provider=lambda: datetime(2026, 9, 17, 13, 20, tzinfo=timezone.utc),
        site_timezone="Europe/Athens",
    )
    intent = planner.understand("ΓΙΑΤΙ ανέβηκε το ΔP χθες;", unit_key="FCC")
    assert intent.period_interpretation == "previous_local_calendar_day"
    assert intent.unit_key == "fcc"


def test_last_24_hours_remains_a_rolling_window():
    planner = InvestigationPlanner(
        now_provider=lambda: datetime(2026, 9, 17, 13, 20, tzinfo=timezone.utc),
        site_timezone="Europe/Athens",
    )
    intent = planner.understand("Δείξε τις τελευταίες 24 ώρες", unit_key="fcc")
    assert intent.period_interpretation == "rolling_24h"
    assert intent.start_time == "2026-09-16T13:20:00+00:00"
    assert intent.end_time == "2026-09-17T13:20:00+00:00"
