from app.process_analytics import detect_deviation, extract_series, pearson, summarize_series


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


def test_extracts_simulator_items_with_pi_style_value_case():
    payload={"Items":[{"Timestamp":"a","Value":1.0},{"Timestamp":"b","Value":2.0},{"Timestamp":"c","Value":3.0}]}
    assert extract_series(payload)==[1.0,2.0,3.0]
    assert summarize_series(payload)["delta"]==2.0


def test_extracts_nested_tool_data_envelope():
    payload={"tag":"regenerator_dp","data":{"Items":[{"Timestamp":"a","Value":0.7},{"Timestamp":"b","Value":0.8}]}}
    assert extract_series(payload)==[0.7,0.8]


def test_correlates_simulator_series():
    left={"Items":[{"Value":1},{"Value":2},{"Value":3},{"Value":4}]}
    right={"Items":[{"Value":2},{"Value":4},{"Value":6},{"Value":8}]}
    result=pearson(left,right)
    assert result["available"] is True
    assert round(result["pearson_r"],6)==1.0
