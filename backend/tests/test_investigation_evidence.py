from backend.app.investigation_evidence import evidence_identity,merge_new_evidence

def test_same_event_is_not_new_twice():
    item={"tool":"search_alarms_events","data":{"event_id":"evt-1","message":"DP high"},"provenance":{"source":"pi"}}
    merged,new=merge_new_evidence([], [item])
    assert len(new)==1
    merged,new=merge_new_evidence(merged,[item])
    assert len(new)==0
    assert len(merged)==1

def test_archive_revision_has_distinct_identity():
    a={"tool":"search_archive","data":{"document_id":"PID-1","revision":"A","page":2}}
    b={"tool":"search_archive","data":{"document_id":"PID-1","revision":"B","page":2}}
    assert evidence_identity(a)!=evidence_identity(b)

def test_history_identity_is_window_specific():
    a={"tool":"get_history","data":{"tag_key":"fcc.dp","start_time":"a","end_time":"b"}}
    b={"tool":"get_history","data":{"tag_key":"fcc.dp","start_time":"b","end_time":"c"}}
    assert evidence_identity(a)!=evidence_identity(b)
