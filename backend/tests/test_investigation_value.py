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


def test_measurement_candidates_rank_focus_match_before_catalog_order():
    from backend.app.investigation_value import rank_measurement_candidates
    ranked=rank_measurement_candidates(
        candidates=[
            {"key":"feed_flow","label":"Feed Flow","semantic_key":"feed_flow","unit":"m3/h"},
            {"key":"regenerator_temp","label":"Regenerator Temperature","semantic_key":"regenerator_temperature","unit":"C"},
            {"key":"regenerator_o2","label":"Regenerator O2","semantic_key":"regenerator_o2","unit":"%"},
        ],
        focus="Investigate regenerator temperature relationship",
        resolved_tags=[],
        limit=3,
    )
    assert ranked[0]["tag_key"]=="regenerator_temp"
    assert ranked[0]["score"] > ranked[-1]["score"]
    assert ranked[0]["reason"]
    assert "regenerator" in ranked[0]["matched_focus_tokens"]


def test_measurement_candidate_ranking_excludes_already_resolved_tags():
    from backend.app.investigation_value import rank_measurement_candidates
    ranked=rank_measurement_candidates(
        candidates=[{"key":"a","label":"Pressure A"},{"key":"b","label":"Pressure B"}],
        focus="pressure",
        resolved_tags=["a"],
    )
    assert [item["tag_key"] for item in ranked]==["b"]


def test_realized_information_gain_rewards_new_series_and_correlations():
    from backend.app.investigation_value import score_evidence_gain
    before={"summaries":{"a":{"count":10}},"correlations":[],"temporal":{}}
    after={
        "summaries":{"a":{"count":10},"b":{"count":10}},
        "correlations":[{"left":"a","right":"b","r":0.7}],
        "temporal":{"b":{"available":True}},
    }
    gain=score_evidence_gain(before_analytics=before,after_analytics=after,tag_key="b")
    assert gain["classification"]=="useful_information_gain"
    assert gain["new_series"] is True
    assert gain["new_correlations"]==1
    assert gain["score"] > 0


def test_realized_information_gain_marks_empty_historian_read():
    from backend.app.investigation_value import score_evidence_gain
    gain=score_evidence_gain(
        before_analytics={"summaries":{},"correlations":[]},
        after_analytics={"summaries":{"x":{"count":0}},"correlations":[],"temporal":{}},
        tag_key="x",
    )
    assert gain["classification"]=="no_usable_data"
    assert gain["score"]==0
