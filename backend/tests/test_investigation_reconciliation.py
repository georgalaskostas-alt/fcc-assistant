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
    assert counts=={"archive_added":0,"events_added":1,"episodes_added":1}
    assert synthesis["event_evidence"]["count"]==1
    assert synthesis["similar_episodes"]["count"]==1
