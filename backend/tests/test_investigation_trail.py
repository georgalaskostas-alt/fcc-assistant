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


def test_trail_preserves_branch_decisions_and_realized_information_gain():
    synthesis={"autonomous_investigation":{"rounds_completed":1,"stop_reason":"iteration_budget_exhausted","rounds":[{
        "round":1,
        "plan":{
            "focus":"pressure-temperature",
            "hypothesis_branches":[{"branch_id":"h1","priority":1,"score":8.0}],
            "actions":[{"tool":"get_history","reason":"new measurement","hypothesis_branch_id":"h1","branch_score":8.0}],
        },
        "hypothesis_branch_lifecycle":[{"branch_id":"h1","state":"keep","score":8.0}],
        "branch_lifecycle_after_evidence":[{"branch_id":"h1","state":"promote","score":8.5}],
        "realized_information_gain":[{"tag_key":"temperature","classification":"useful_information_gain","score":5.25}],
        "new_evidence_count":1,
    }]}}
    trail=build_investigation_trail(goal="why",synthesis=synthesis,hypotheses=[])
    entry=trail["entries"][0]
    assert entry["hypothesis_branches"][0]["branch_id"]=="h1"
    assert entry["branch_lifecycle"][0]["state"]=="keep"
    assert entry["branch_lifecycle_after_evidence"][0]["state"]=="promote"
    assert entry["actions"][0]["hypothesis_branch_id"]=="h1"
    assert entry["realized_information_gain"][0]["classification"]=="useful_information_gain"


def test_trail_builds_explicit_hypothesis_evidence_graph():
    hypotheses=[{
        "id":"h1","statement":"Investigate DP and temperature","evidence_status":"supporting_independent_evidence",
        "causal_status":"not_established",
        "supporting_independent_evidence":[{"evidence_id":"doc:1","tool":"search_archive","description":"Approved troubleshooting note","provenance":{"revision":"B"}}],
        "contradicting_independent_evidence":[{"evidence_id":"event:2","tool":"search_alarms_events","description":"Alarm sequence","provenance":{"event_id":"2"}}],
        "missing_evidence":[],
    }]
    trail=build_investigation_trail(goal="why",synthesis={},hypotheses=hypotheses)
    graph=trail["evidence_graph"]
    assert any(n["id"]=="h1" and n["kind"]=="hypothesis" for n in graph["nodes"])
    assert any(n["id"]=="doc:1" and n["source_kind"]=="technical_archive" for n in graph["nodes"])
    assert {"from":"doc:1","to":"h1","relation":"supports"} in graph["edges"]
    assert {"from":"event:2","to":"h1","relation":"contradicts"} in graph["edges"]
