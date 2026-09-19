from backend.app.investigation_trail import build_investigation_trail

def test_trail_records_hypotheses_rounds_and_stop_reason():
    synthesis={"evidence_count":9,"autonomous_investigation":{"rounds_completed":1,"stop_reason":"no_new_evidence","rounds":[
        {"round":1,"plan":{"focus":"dp-o2","actions":[{"tool":"search_archive","reason":"need mechanism"}]},"new_evidence_count":2}
    ]}}
    hypotheses=[{"id":"h1","statement":"dp-o2","evidence_status":"mixed_independent_evidence",
        "supporting_independent_evidence":[{"id":"a"}],"contradicting_independent_evidence":[{"id":"b"}],
        "missing_evidence":["operating context"],"causal_status":"not_established"}]
    trail=build_investigation_trail(goal="why",synthesis=synthesis,hypotheses=hypotheses)
    assert trail["rounds_completed"] == 1
    assert trail["stop_reason"] == "no_new_evidence"
    assert trail["entries"][0]["supporting_count"] == 1
    assert trail["entries"][0]["contradicting_count"] == 1
    assert trail["entries"][1]["actions"][0]["tool"] == "search_archive"
    assert trail["causal_conclusion"] == "not_established"
    assert trail["process_control_actions_allowed"] is False
