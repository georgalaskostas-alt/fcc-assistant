from backend.app.investigation_sources import collect_canonical_sources, resolve_source_ids, source_drilldown

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


def test_resolves_only_real_canonical_source_ids():
    sources=[{"evidence_id":"history:fcc.feed:a:b"},{"evidence_id":"archive:DOC-1:A:3"}]
    refs=[{"evidence_id":"archive:DOC-1:A:3"},"missing",{"stable_evidence_id":"history:fcc.feed:a:b"}]
    assert resolve_source_ids(refs,sources)==["archive:DOC-1:A:3","history:fcc.feed:a:b"]


def test_source_drilldown_preserves_document_revision_and_page():
    source={"evidence_id":"d1","source_kind":"technical_archive","description":"WGC manual","provenance":{"document_id":"DOC-1","revision":"B","page":12},"data":{"title":"Wet Gas Compressor Manual","text":"Relevant approved excerpt"}}
    detail=source_drilldown(source)
    assert detail["read_only"] is True
    assert detail["document"]["document_id"]=="DOC-1"
    assert detail["document"]["revision"]=="B"
    assert detail["document"]["page"]==12

def test_source_drilldown_exposes_historian_window_and_points():
    source={"evidence_id":"h1","source_kind":"historian","provenance":{"tag_key":"fcc.feed","start_time":"a","end_time":"b"},"data":{"points":[{"x":"a","y":1.0},{"x":"b","y":2.0}]}}
    detail=source_drilldown(source)
    assert detail["historian"]["tag_key"]=="fcc.feed"
    assert detail["historian"]["start_time"]=="a"
    assert len(detail["historian"]["points"])==2
