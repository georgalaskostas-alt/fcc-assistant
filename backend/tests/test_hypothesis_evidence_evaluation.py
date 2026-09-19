from backend.app.investigation_hypotheses import evaluate_hypotheses


def test_independent_sources_are_available_but_do_not_prove_causality():
    hypotheses = [{"id":"h1","causal_status":"not_established","missing_evidence":["x"]}]
    synthesis = {
        "archive_evidence": {"items":[{"document_id":"M-1"}]},
        "event_evidence": {"count":2},
        "similar_episodes": {"items":[{"episode":{"id":"e1"}}]},
    }
    result = evaluate_hypotheses(hypotheses=hypotheses, synthesis=synthesis)[0]
    assert result["evidence_status"] == "independent_evidence_available"
    assert len(result["independent_evidence"]) == 3
    assert result["missing_evidence"] == []
    assert result["causal_status"] == "not_established"


def test_missing_independent_sources_are_explicit():
    result = evaluate_hypotheses(hypotheses=[{"id":"h1"}], synthesis={})[0]
    assert result["evidence_status"] == "insufficient_independent_evidence"
    assert len(result["missing_evidence"]) == 3
    assert result["causal_status"] == "not_established"
