from backend.app.evidence_matching import match_hypothesis_evidence
from backend.app.investigation_hypotheses import evaluate_hypotheses


def test_archive_match_requires_specific_shared_terms():
    hypothesis = {"statement":"Investigate relationship between regenerator_dp and regenerator_o2"}
    synthesis = {"archive_evidence":{"items":[
        {"document_id":"M1","revision":"C","title":"Regenerator troubleshooting","text":"regenerator_dp high with regenerator_o2 response","page":7},
        {"document_id":"M2","revision":"A","title":"Pump manual","text":"lubrication bearing"}
    ]}}
    result = match_hypothesis_evidence(hypothesis=hypothesis, synthesis=synthesis)
    assert result["match_count"] == 1
    assert result["matches"][0]["document_id"] == "M1"


def test_specific_match_still_does_not_establish_causality():
    hypotheses = [{"statement":"Investigate relationship between regenerator_dp and regenerator_o2"}]
    synthesis = {"archive_evidence":{"items":[{"document_id":"M1","text":"regenerator_dp and regenerator_o2","title":"","revision":"C"}]}}
    result = evaluate_hypotheses(hypotheses=hypotheses, synthesis=synthesis)[0]
    assert result["evidence_status"] == "specific_independent_evidence_found"
    assert result["causal_status"] == "not_established"
