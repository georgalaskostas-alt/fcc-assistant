from backend.app.investigation_followup import plan_follow_up

def test_follow_up_targets_missing_evidence_and_is_bounded():
    plan = plan_follow_up(
        goal="why dp changed", unit_key="fcc",
        synthesis={"archive_evidence":{"count":0},"event_evidence":{"count":0},"similar_episodes":{"count":0}},
        hypotheses=[{"evidence_status":"insufficient_independent_evidence"}],
        max_actions=2,
    )
    assert plan["needed"] is True
    assert len(plan["actions"]) == 2
    assert all(a["tool"] in {"search_archive","search_alarms_events","find_similar_episodes"} for a in plan["actions"])
    assert plan["process_control_actions_allowed"] is False

def test_follow_up_stops_when_independent_evidence_is_specific():
    plan = plan_follow_up(
        goal="why", unit_key="fcc",
        synthesis={"archive_evidence":{"count":1},"event_evidence":{"count":1},"similar_episodes":{"count":1}},
        hypotheses=[{"evidence_status":"supporting_independent_evidence"}],
    )
    assert plan["needed"] is False
    assert plan["actions"] == []
