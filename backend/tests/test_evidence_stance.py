from backend.app.evidence_matching import match_hypothesis_evidence
from backend.app.investigation_hypotheses import evaluate_hypotheses


def _hypothesis():
    return {"statement":"Investigate relationship between regenerator_dp and regenerator_o2"}


def test_supporting_archive_evidence_is_separated():
    synthesis={"archive_evidence":{"items":[{"document_id":"M1","text":"regenerator_dp increased with regenerator_o2 response"}]}}
    result=match_hypothesis_evidence(hypothesis=_hypothesis(),synthesis=synthesis)
    assert len(result["supporting"]) == 1
    assert not result["contradicting"]


def test_contradicting_archive_evidence_is_separated():
    synthesis={"archive_evidence":{"items":[{"document_id":"M2","text":"regenerator_dp and regenerator_o2 unrelated without response"}]}}
    result=match_hypothesis_evidence(hypothesis=_hypothesis(),synthesis=synthesis)
    assert len(result["contradicting"]) == 1


def test_mixed_evidence_stays_unresolved():
    synthesis={"archive_evidence":{"items":[
        {"document_id":"M1","text":"regenerator_dp increased with regenerator_o2 response"},
        {"document_id":"M2","text":"regenerator_dp and regenerator_o2 unrelated without response"},
    ]}}
    result=evaluate_hypotheses(hypotheses=[_hypothesis()],synthesis=synthesis)[0]
    assert result["evidence_status"] == "mixed_independent_evidence"
    assert result["causal_status"] == "not_established"
