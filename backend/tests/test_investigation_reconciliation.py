from backend.app.investigation_reconciliation import reconcile_follow_up

def _run(tool,data):
    return {"executions":[{"step":{"tool_name":tool},"status":"succeeded","result":{"data":data}}]}

def test_reconciles_archive_for_next_round():
    synthesis={"archive_evidence":{}}
    result={"run":_run("search_archive",[{"document_id":"D1","revision":"A","text":"regenerator dp"}])}
    counts=reconcile_follow_up(synthesis,result)
    assert counts["archive_added"]==1
    assert synthesis["archive_evidence"]["count"]==1
    assert synthesis["archive_evidence_useful"] is True

def test_reconciles_events_and_episodes():
    synthesis={}
    run={"executions":[
      {"step":{"tool_name":"search_alarms_events"},"status":"succeeded","result":{"data":[{"id":"E1"}]}},
      {"step":{"tool_name":"find_similar_episodes"},"status":"succeeded","result":{"data":[{"episode":{"id":"P1"},"similarity":.8}]}}
    ]}
    counts=reconcile_follow_up(synthesis,{"run":run})
    assert counts=={"archive_added":0,"events_added":1,"episodes_added":1,"tags_added":0,"histories_added":0}
    assert synthesis["event_evidence"]["count"]==1
    assert synthesis["similar_episodes"]["count"]==1


def test_reconciles_discovered_tags_and_history_without_duplicates():
    synthesis={}
    run={"executions":[
      {"step":{"tool_name":"search_tags"},"status":"succeeded","result":{"data":[{"key":"regenerator_dp","label":"Regenerator DP"}]}},
      {"step":{"tool_name":"get_history"},"status":"succeeded","result":{"data":{"tag_key":"regenerator_dp","start_time":"s","end_time":"e","data":[1,2,3]}}}
    ]}
    counts=reconcile_follow_up(synthesis,{"run":run})
    assert counts["tags_added"]==1
    assert counts["histories_added"]==1
    assert synthesis["discovered_tags"]["items"][0]["key"]=="regenerator_dp"
    assert synthesis["history_evidence"]["count"]==1


def test_reconciliation_queues_discovered_tags_by_information_value():
    synthesis={"goal":"Investigate regenerator temperature","resolved_tags":[]}
    run={"executions":[{
      "step":{"tool_name":"search_tags"},"status":"succeeded",
      "result":{"data":[
        {"key":"feed_flow","label":"Feed Flow","semantic_key":"feed_flow","unit":"m3/h"},
        {"key":"regenerator_temp","label":"Regenerator Temperature","semantic_key":"regenerator_temperature","unit":"C"},
      ]}
    }]}
    reconcile_follow_up(synthesis,{"run":run})
    assert synthesis["pending_history_tags"][0]=="regenerator_temp"
    assert synthesis["measurement_candidate_ranking"][0]["tag_key"]=="regenerator_temp"
