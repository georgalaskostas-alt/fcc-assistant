from backend.app.investigation_conclusion import build_evidence_aware_conclusion


def test_conclusion_separates_supported_contradicted_and_unresolved():
    analytics={"summaries":{"dp":{"count":10,"mean":2.1,"min":1.8,"max":2.5,"delta":0.4,"evidence_id":"e-dp"}}}
    hypotheses=[
        {"id":"supported","statement":"A","evidence_status":"supporting_independent_evidence","supporting_independent_evidence":[{"id":"doc1"}],"contradicting_independent_evidence":[],"missing_evidence":[]},
        {"id":"contradicted","statement":"B","evidence_status":"contradicting_independent_evidence","supporting_independent_evidence":[],"contradicting_independent_evidence":[{"id":"event1"}],"missing_evidence":["context"]},
        {"id":"open","statement":"C","evidence_status":"mixed_independent_evidence","supporting_independent_evidence":[{"id":"doc2"}],"contradicting_independent_evidence":[{"id":"event2"}],"missing_evidence":["history"]},
    ]
    synthesis={"evidence_package":[{"stable_evidence_id":"history:dp:s:e","tool":"get_history","description":"DP history","provenance":{"tag_key":"dp"}}]}
    result=build_evidence_aware_conclusion(analytics=analytics,hypotheses=hypotheses,synthesis=synthesis)
    assert result["observed_facts"][0]["tag_key"]=="dp"
    assert result["supported_explanations"][0]["hypothesis_id"]=="supported"
    assert result["contradicted_explanations"][0]["hypothesis_id"]=="contradicted"
    assert result["unresolved_explanations"][0]["hypothesis_id"]=="open"
    assert result["overall_causal_conclusion"]=="not_established"
    assert result["process_control_actions_allowed"] is False


def test_confidence_is_evidence_sufficiency_not_causal_probability():
    result=build_evidence_aware_conclusion(
        analytics={"summaries":{}},
        hypotheses=[{"id":"h","statement":"A","supporting_independent_evidence":[{"id":"a"},{"id":"b"}],"contradicting_independent_evidence":[],"missing_evidence":[]}],
        synthesis={},
    )
    confidence=result["supported_explanations"][0]["confidence"]
    assert confidence["level"]=="moderate"
    assert "not probability of causation" in confidence["meaning"]
    assert result["limitations"]
