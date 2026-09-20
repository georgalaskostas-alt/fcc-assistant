from backend.app.investigation_value import rank_hypotheses,choose_next_evidence_actions

def test_ranks_larger_evidence_gap_first():
    hs=[
      {"id":"h1","evidence_status":"supporting_independent_evidence","causal_status":"not_established","association":{"strength":.9},"missing_evidence":[]},
      {"id":"h2","evidence_status":"insufficient_independent_evidence","causal_status":"not_established","association":{"strength":.7},"missing_evidence":["Approved technical-archive evidence","Relevant alarms/events"]}
    ]
    ranked=rank_hypotheses(hs)
    assert ranked[0]["hypothesis"]["id"]=="h2"

def test_prefers_archive_and_events_for_explicit_gaps():
    h={"missing_evidence":["Approved technical-archive evidence","Relevant alarms/events"]}
    actions=choose_next_evidence_actions(hypothesis=h,synthesis={"similar_episodes":{"count":1}},unit_key="fcc",query="regenerator dp")
    assert [a["tool"] for a in actions]==["search_archive","search_alarms_events"]
    assert actions[0]["value"]>actions[1]["value"]
