from backend.app.investigation_reasoning import _reasoning_context


def test_reasoning_context_carries_independent_evidence():
    synthesis = {
        "time_window": {"start": "a", "end": "b"},
        "resolved_tags": ["dp"],
        "archive_evidence": {"count": 1, "items": [{"document_id": "PID-1", "revision": "C"}]},
        "event_evidence": {"count": 2},
        "similar_episodes": {"count": 1},
        "limitations": [],
    }
    context = _reasoning_context(goal="why", synthesis=synthesis, data_source={"mode": "local"}, analytics={})
    assert context["archive_evidence"]["count"] == 1
    assert context["event_evidence"]["count"] == 2
    assert context["similar_episodes"]["count"] == 1
