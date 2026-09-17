from backend.app.investigation_reasoning import _reasoning_context, build_deterministic_analytics


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
    left = [{"Value": float(i)} for i in range(10)]
    right = [{"Value": float(i * 2)} for i in range(10)]
    synthesis = {"evidence_package": [
        {"evidence_id": "get_history:history-0", "tool": "get_history", "description": "Retrieve read-only historian evidence for regenerator_dp.", "data": {"Items": left}},
        {"evidence_id": "get_history:history-1", "tool": "get_history", "description": "Retrieve read-only historian evidence for regenerator_temp.", "data": {"Items": right}},
    ]}
    analytics = build_deterministic_analytics(synthesis)
    correlation = analytics["correlations"][0]
    assert correlation["left"] == "regenerator_dp"
    assert correlation["right"] == "regenerator_temp"
    assert correlation["left_evidence_id"] == "get_history:history-0"
    assert correlation["right_evidence_id"] == "get_history:history-1"
