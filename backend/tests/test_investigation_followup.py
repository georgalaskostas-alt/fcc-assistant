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


def test_goal_discovery_uses_only_previously_discovered_tag_keys_for_history():
    plan = plan_follow_up(
        goal="Why did regenerator DP increase?",
        unit_key="fcc",
        synthesis={
            "time_window": {"start": "2026-09-20T00:00:00Z", "end": "2026-09-21T00:00:00Z"},
            "discovered_tags": {"items": [
                {"key": "regenerator_dp", "label": "Regenerator Differential Pressure"},
                {"key": "regenerator_temp", "label": "Regenerator Temperature"},
            ]},
        },
        hypotheses=[],
        max_actions=3,
        round_index=1,
    )

    assert plan["needed"] is True
    assert plan["planning_mode"] == "goal_discovery"
    history = [action for action in plan["actions"] if action["tool"] == "get_history"]
    assert [action["arguments"]["tag_key"] for action in history] == ["regenerator_dp", "regenerator_temp"]
    assert all(action["arguments"]["start_time"] == "2026-09-20T00:00:00Z" for action in history)
    assert all(action["arguments"]["end_time"] == "2026-09-21T00:00:00Z" for action in history)
    assert not any(action["tool"] == "search_tags" for action in plan["actions"])


def test_unresolved_hypothesis_can_discover_additional_governed_measurements():
    hypothesis={
        "id":"h1",
        "statement":"Investigate the observed relationship between A and B.",
        "causal_status":"not_established",
        "evidence_status":"specific_independent_evidence_found",
        "association":{"strength":0.8},
        "missing_evidence":["Additional operating context"],
    }
    plan=plan_follow_up(
        goal="Why did pressure increase?",
        unit_key="fcc",
        synthesis={
            "archive_evidence":{"count":1},
            "event_evidence":{"count":1},
            "similar_episodes":{"count":1},
            "resolved_tags":["tag_a"],
            "discovered_tags":{"items":[{"key":"tag_b"}]},
        },
        hypotheses=[hypothesis],
        max_actions=3,
        round_index=1,
    )
    discovery=[a for a in plan["actions"] if a["tool"]=="search_tags"]
    assert discovery
    assert discovery[0]["arguments"]["query"]==hypothesis["statement"]
    assert discovery[0]["exclude_tag_keys"]==["tag_a","tag_b"]
    assert plan["process_control_actions_allowed"] is False


def test_newly_discovered_hypothesis_tags_are_read_from_historian_next_round():
    hypothesis={
        "id":"h1",
        "statement":"Investigate A and B",
        "causal_status":"not_established",
        "evidence_status":"relevant_but_insufficient",
        "association":{"strength":0.7},
        "missing_evidence":["Additional operating context"],
    }
    plan=plan_follow_up(
        goal="why",
        unit_key="fcc",
        synthesis={
            "time_window":{"start":"2026-09-20T00:00:00Z","end":"2026-09-21T00:00:00Z"},
            "pending_history_tags":["new_tag_1","new_tag_2"],
            "resolved_tags":["old_tag"],
        },
        hypotheses=[hypothesis],
        max_actions=3,
        round_index=2,
    )
    assert plan["planning_mode"]=="new_measurement_history"
    assert [a["tool"] for a in plan["actions"]]==["get_history","get_history"]
    assert [a["arguments"]["tag_key"] for a in plan["actions"]]==["new_tag_1","new_tag_2"]
    assert all(a["arguments"]["start_time"]=="2026-09-20T00:00:00Z" for a in plan["actions"])
