from pathlib import Path
import json

from backend.app.operational_events import OperationalEventStore


def test_event_store_filters_unit_window_and_query(tmp_path: Path):
    path = tmp_path / "events.json"
    path.write_text(json.dumps([
        {"id":"1","unit_key":"fcc","timestamp":"2026-09-19T01:00:00+00:00","event_type":"alarm","source":"demo","message":"high pressure","severity":"high"},
        {"id":"2","unit_key":"hcu","timestamp":"2026-09-19T01:00:00+00:00","event_type":"alarm","source":"demo","message":"high pressure","severity":"high"},
        {"id":"3","unit_key":"fcc","timestamp":"2026-09-20T01:00:00+00:00","event_type":"alarm","source":"demo","message":"high pressure","severity":"high"},
    ]), encoding="utf-8")
    store = OperationalEventStore(path)
    hits = store.search(unit_key="fcc", start_time="2026-09-19T00:00:00+00:00", end_time="2026-09-19T23:00:00+00:00", query="pressure")
    assert [item["id"] for item in hits] == ["1"]
