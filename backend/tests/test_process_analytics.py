from app.process_analytics import detect_deviation, pearson, summarize_series


def test_summary_is_deterministic():
    result = summarize_series({"values": [{"value": 10}, {"value": 12}, {"value": 14}]})
    assert result["count"] == 3
    assert result["mean"] == 12
    assert result["delta"] == 4


def test_correlation_warns_association_is_not_causation():
    result = pearson([1,2,3,4], [2,4,6,8])
    assert result["pearson_r"] > .99
    assert "not proof of causation" in result["warning"]


def test_deviation_requires_evidence():
    result = detect_deviation([1,2,3])
    assert result["available"] is False
