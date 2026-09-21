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


def test_goal_discovery_bootstraps_when_no_hypothesis_exists():
    plan = plan_follow_up(
        goal="Why did regenerator DP increase?",
        unit_key="fcc",
        synthesis={"time_window": {"start": "2026-09-20T00:00:00Z", "end": "2026-09-21T00:00:00Z"}},
        hypotheses=[],
        max_actions=3,
        round_index=0,
    )

    assert plan["needed"] is True
    assert plan["planning_mode"] == "goal_discovery"
    tools = [action["tool"] for action in plan["actions"]]
    assert tools == ["search_tags", "search_alarms_events", "search_archive"]
    assert plan["selected_hypothesis_id"] is None
    assert plan["process_control_actions_allowed"] is False
