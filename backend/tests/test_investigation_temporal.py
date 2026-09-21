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
