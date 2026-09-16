from backend.app.investigation_reasoning import _reasoning_context, build_deterministic_analytics


def test_reasoning_context_does_not_include_raw_historian_arrays():
    samples = [{"Timestamp": f"t{i}", "Value": float(i)} for i in range(2000)]
    synthesis = {
        "ready_for_reasoning": True,
        "resolved_tags": ["regenerator_o2"],
        "time_window": {"start": "a", "end": "b"},
        "limitations": [],
        "discovery_evidence": [{"evidence_id": "search_tags:resolve-tags", "tool": "search_tags", "data": [{"key": "regenerator_o2", "label": "O2"}], "provenance": {"source": "registry"}}],
        "evidence_package": [{"evidence_id": "get_history:history-0", "tool": "get_history", "data": {"values": samples}, "provenance": {"source": "simulator"}}],
    }
    analytics = build_deterministic_analytics(synthesis)
    context = _reasoning_context(goal="why", synthesis=synthesis, data_source={"mode": "simulated", "data_quality": "SIMULATED"}, analytics=analytics)
    assert "evidence" not in context
    assert context["history_evidence_ids"] == ["get_history:history-0"]
    assert context["deterministic_analytics"]["summaries"]["get_history:history-0"]["count"] == 2000
    assert "t1999" not in str(context)
