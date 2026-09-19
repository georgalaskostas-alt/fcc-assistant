from backend.app.investigation_hypotheses import build_hypothesis_candidates, investigation_stop_decision


def test_hypothesis_contract_never_asserts_causality():
    analytics = {
        "correlations": [{
            "left": "a", "right": "b", "r": 0.91,
            "left_evidence_id": "e1", "right_evidence_id": "e2",
            "lagged": {"available": True, "lag_samples": 2, "r": 0.95},
        }],
        "temporal": {"a": {"onset_index": 20}, "b": {"onset_index": 30}},
    }
    items = build_hypothesis_candidates(analytics)
    assert len(items) == 1
    item = items[0]
    assert item["causal_status"] == "not_established"
    assert item["supporting_evidence_ids"] == ["e1", "e2"]
    assert item["missing_evidence"]
    assert "Investigate whether" in item["statement"]


def test_stop_decision_reports_current_tool_boundary():
    decision = investigation_stop_decision(
        synthesis={"adaptive_evidence": {"attempted": True, "additional_tags": ["c"]}, "archive_evidence_useful": False},
        analytics={},
        hypotheses=[{"causal_status": "not_established"}],
    )
    assert decision["stop"] is True
    assert decision["reason"] == "evidence_boundary_reached"
    assert decision["safe_to_assert_causality"] is False
    assert "search_alarms_events" in decision["next_tools_needed"]
