from backend.app.investigation_reasoning import _reasoning_context, build_deterministic_analytics, build_structured_claims, validate_reasoning_text


def test_reasoning_context_does_not_include_raw_historian_arrays():
    samples = [{"Timestamp": f"t{i}", "Value": float(i)} for i in range(2000)]
    synthesis = {
        "ready_for_reasoning": True,
        "resolved_tags": ["regenerator_o2"],
        "time_window": {"start": "a", "end": "b"},
        "limitations": [],
        "discovery_evidence": [{"evidence_id": "search_tags:resolve-tags", "tool": "search_tags", "data": [{"key": "regenerator_o2", "label": "O2"}], "provenance": {"source": "registry"}}],
        "evidence_package": [{"evidence_id": "get_history:history-0", "tool": "get_history", "description": "Retrieve read-only historian evidence for regenerator_o2.", "data": {"values": samples}, "provenance": {"source": "simulator"}}],
    }
    analytics = build_deterministic_analytics(synthesis)
    context = _reasoning_context(goal="why", synthesis=synthesis, data_source={"mode": "simulated", "data_quality": "SIMULATED"}, analytics=analytics)
    assert "history_evidence_ids" not in context
    assert context["deterministic_analytics"]["summaries"]["regenerator_o2"]["count"] == 2000
    assert context["deterministic_analytics"]["summaries"]["regenerator_o2"]["evidence_id"] == "get_history:history-0"
    assert "t1999" not in str(context)


def test_correlations_use_semantic_tag_labels_and_keep_evidence_ids():
    left = [{"Value": float(i)} for i in range(10)]; right = [{"Value": float(i * 2)} for i in range(10)]
    synthesis = {"evidence_package": [
        {"evidence_id": "get_history:history-0", "tool": "get_history", "description": "Retrieve read-only historian evidence for regenerator_dp.", "data": {"Items": left}},
        {"evidence_id": "get_history:history-1", "tool": "get_history", "description": "Retrieve read-only historian evidence for regenerator_temp.", "data": {"Items": right}},
    ]}
    correlation = build_deterministic_analytics(synthesis)["correlations"][0]
    assert correlation["left"] == "regenerator_dp"; assert correlation["right"] == "regenerator_temp"
    assert correlation["left_evidence_id"] == "get_history:history-0"; assert correlation["right_evidence_id"] == "get_history:history-1"


def test_structured_claims_bind_facts_and_associations_to_evidence():
    analytics = {
        "summaries": {"regenerator_dp": {"evidence_id": "get_history:history-0", "count": 10, "mean": 0.75, "min": 0.70, "max": 0.84, "first": 0.72, "last": 0.84, "delta": 0.12}},
        "correlations": [{"left": "regenerator_dp", "right": "regenerator_temp", "r": 0.968, "left_evidence_id": "get_history:history-0", "right_evidence_id": "get_history:history-1"}],
    }
    claims = build_structured_claims(analytics, data_quality="SIMULATED")
    fact = claims[0]; association = claims[1]
    assert fact["type"] == "measured_fact" and fact["evidence_ids"] == ["get_history:history-0"]
    assert fact["evidence_status"] == "simulated" and fact["confidence"] == "high"
    assert association["type"] == "association"
    assert association["evidence_ids"] == ["get_history:history-0", "get_history:history-1"]
    assert "does not establish causation" in association["statement"]
    assert association["required_evidence"]


def test_structured_claims_do_not_manufacture_mechanistic_hypotheses():
    claims = build_structured_claims({"summaries": {}, "correlations": []}, data_quality="HISTORIAN")
    assert claims == []


def test_validator_rejects_unsupported_causal_claim():
    result = validate_reasoning_text("Temperature rise drove DP increase. However, correlation is not causation.")
    assert result["valid"] is False
    assert any(item["type"] == "unsupported_causality" for item in result["violations"])


def test_validator_rejects_statistical_significance_without_test_contract():
    result = validate_reasoning_text("No statistically significant deviations were observed.")
    assert result["valid"] is False
    assert any(item["type"] == "unsupported_statistical_significance" for item in result["violations"])


def test_validator_allows_association_language():
    result = validate_reasoning_text("Regenerator temperature was strongly associated with DP (Pearson r=0.968). This does not establish causation.")
    assert result == {"valid": True, "violations": []}


def test_validator_rejects_process_control_action():
    result = validate_reasoning_text("Increase the controller setpoint to reduce the deviation.")
    assert result["valid"] is False
    assert any(item["type"] == "process_control_action" for item in result["violations"])


def test_extrema_with_timestamps_are_deterministic():
    from backend.app.investigation_reasoning import _extrema_with_timestamps

    payload = {
        "values": [
            {"timestamp": "2026-09-21T00:00:00+03:00", "value": 0.72},
            {"timestamp": "2026-09-21T08:15:00+03:00", "value": 0.9281},
            {"timestamp": "2026-09-21T12:30:00+03:00", "value": 0.6955},
            {"timestamp": "2026-09-21T23:59:00+03:00", "value": 0.84},
        ]
    }

    result = _extrema_with_timestamps(payload)

    assert result["max"] == 0.9281
    assert result["max_timestamp"] == "2026-09-21T08:15:00+03:00"
    assert result["min"] == 0.6955
    assert result["min_timestamp"] == "2026-09-21T12:30:00+03:00"
