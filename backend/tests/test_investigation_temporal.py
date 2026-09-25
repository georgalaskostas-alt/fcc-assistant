from app.process_analytics import lagged_pearson, temporal_profile
from app.investigation_reasoning import build_deterministic_analytics


def test_temporal_profile_reports_direction_and_onset():
    payload = [{"Value": value} for value in [1,1,1,1,1,2,3,4,5,6,7,8]]
    result = temporal_profile(payload)
    assert result["available"] is True
    assert result["direction"] == "increasing"
    assert result["onset_index"] is not None


def test_lagged_pearson_reports_descriptive_best_lag():
    left = [{"Value": value} for value in range(20)]
    right = [{"Value": 0}, {"Value": 0}] + [{"Value": value} for value in range(18)]
    result = lagged_pearson(left, right, max_lag=4)
    assert result["available"] is True
    assert "lag_samples" in result
    assert "causation" in result["warning"]


def test_real_historian_payload_keeps_tag_identity_in_analytics():
    synthesis={"evidence_package":[{
        "evidence_id":"get_history:1",
        "tool":"get_history",
        "description":"Autonomous evidence follow-up.",
        "data":{
            "tag":{"key":"regenerator_dp","name":"Regenerator DP"},
            "range":{"start_time":"s","end_time":"e"},
            "data":{"Items":[{"Value":1.0},{"Value":2.0},{"Value":3.0}]},
        },
        "provenance":{},
    }]}
    analytics=build_deterministic_analytics(synthesis)
    assert "regenerator_dp" in analytics["summaries"]
    assert analytics["summaries"]["regenerator_dp"]["count"]==3

def test_planner_resolves_greek_yesterday_as_previous_local_calendar_day():
    from datetime import datetime, timezone
    from app.investigation_planner import InvestigationPlanner

    planner = InvestigationPlanner(
        now_provider=lambda: datetime(2026, 9, 22, 7, 41, 16, tzinfo=timezone.utc),
        site_timezone="Europe/Athens",
    )

    intent = planner.understand(
        "Γιατί ανέβηκε το ΔP του regenerator χθες;",
        unit_key="fcc",
    )

    assert intent.period_interpretation == "previous_local_calendar_day"
    assert intent.start_time == "2026-09-20T21:00:00+00:00"
    assert intent.end_time == "2026-09-21T21:00:00+00:00"


def test_planner_resolves_english_yesterday_as_previous_local_calendar_day():
    from datetime import datetime, timezone
    from app.investigation_planner import InvestigationPlanner

    planner = InvestigationPlanner(
        now_provider=lambda: datetime(2026, 9, 22, 7, 41, 16, tzinfo=timezone.utc),
        site_timezone="Europe/Athens",
    )

    intent = planner.understand(
        "Why did regenerator DP increase yesterday?",
        unit_key="fcc",
    )

    assert intent.period_interpretation == "previous_local_calendar_day"
    assert intent.start_time == "2026-09-20T21:00:00+00:00"
    assert intent.end_time == "2026-09-21T21:00:00+00:00"
