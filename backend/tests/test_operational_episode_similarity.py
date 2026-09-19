from pathlib import Path

from backend.app.operational_episode import OperationalEpisodeStore


def test_similar_episode_search_is_unit_and_configuration_scoped(tmp_path: Path):
    store = OperationalEpisodeStore(tmp_path / "episodes.json")
    store.add(unit_key="fcc", start_time="2026-09-01T00:00:00+00:00", end_time="2026-09-01T01:00:00+00:00",
              kind="disturbance", regime="normal", operating_state={"dp": 1.2}, configuration_version="current")
    store.add(unit_key="hcu", start_time="2026-09-01T00:00:00+00:00", end_time="2026-09-01T01:00:00+00:00",
              kind="disturbance", regime="normal", operating_state={"dp": 1.2}, configuration_version="current")
    store.add(unit_key="fcc", start_time="2026-08-01T00:00:00+00:00", end_time="2026-08-01T01:00:00+00:00",
              kind="disturbance", regime="normal", operating_state={"dp": 1.2}, configuration_version="old")
    hits = store.similar(unit_key="fcc", context={"state.dp": 1.1}, configuration_version="current")
    assert len(hits) == 1
    assert hits[0].episode.unit_key == "fcc"
    assert hits[0].episode.configuration_version == "current"
