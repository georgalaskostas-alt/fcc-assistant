from app.process_analytics import lagged_pearson, temporal_profile


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
