from backend.app.investigation_sources import collect_canonical_sources

def test_collects_and_deduplicates_sources_across_investigation_state():
    history={"tool":"get_history","evidence_id":"h1","data":{"tag_key":"fcc.feed","start_time":"a","end_time":"b"},"provenance":{"tag_key":"fcc.feed"}}
    archive={"tool":"search_archive","evidence_id":"d1","data":{"document_id":"DOC-1","revision":"A","page":3},"provenance":{"document_id":"DOC-1","revision":"A","page":3}}
    event={"tool":"search_alarms_events","evidence_id":"e1","data":{"event_id":"EV-1"},"provenance":{"unit_key":"fcc"}}
    synthesis={"evidence_package":[history,archive],"discovery_evidence":[archive],"event_evidence":{"items":[event]},"archive_evidence":{"items":[archive]}}
    sources=collect_canonical_sources(synthesis)
    assert len(sources)==3
    assert {s["source_kind"] for s in sources}=={"historian","technical_archive","alarms_events"}
    assert all(s["evidence_id"] for s in sources)
    assert next(s for s in sources if s["source_kind"]=="technical_archive")["provenance"]["revision"]=="A"
