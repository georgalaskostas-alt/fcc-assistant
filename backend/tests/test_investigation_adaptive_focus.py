from backend.app.investigation_followup import plan_follow_up

def test_later_round_focuses_on_unresolved_hypothesis():
    hypothesis={"statement":"Investigate whether regenerator_dp and regenerator_o2 have an independent process explanation.",
                "evidence_status":"relevant_but_insufficient"}
    plan=plan_follow_up(goal="why did dp rise",unit_key="fcc",
        synthesis={"archive_evidence":{"count":1},"event_evidence":{"count":1},"similar_episodes":{"count":1}},
        hypotheses=[hypothesis],round_index=1)
    assert plan["needed"] is True
    assert plan["focus"] == hypothesis["statement"]
    archive=[a for a in plan["actions"] if a["tool"]=="search_archive"][0]
    assert archive["arguments"]["query"] == hypothesis["statement"]

def test_first_round_keeps_original_goal_as_focus():
    plan=plan_follow_up(goal="why did dp rise",unit_key="fcc",
        synthesis={"archive_evidence":{"count":0},"event_evidence":{"count":0},"similar_episodes":{"count":0}},
        hypotheses=[],round_index=0)
    assert plan["focus"] == "why did dp rise"
