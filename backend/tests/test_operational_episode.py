from pathlib import Path

from app.operational_episode import OperationalEpisodeStore, outcome_envelope


def test_similar_episodes_compare_same_configuration(tmp_path: Path):
    store = OperationalEpisodeStore(tmp_path / "episodes.json")
    store.add(
        unit_key="fcc",
        start_time="2026-08-01T07:00:00+00:00",
        end_time="2026-08-01T11:00:00+00:00",
        kind="stable",
        regime="high rate",
        configuration_version="revamp-2025",
        inputs={"feed_rate": 280.0, "feed_family": "A"},
        operating_state={"severity": 1.05},
        outputs={"naphtha_rate": 82.0, "lcco_rate": 38.0},
        quality={"ron": 94.1},
    )
    store.add(
        unit_key="fcc",
        start_time="2024-08-01T07:00:00+00:00",
        end_time="2024-08-01T11:00:00+00:00",
        kind="stable",
        regime="high rate",
        configuration_version="pre-revamp",
        inputs={"feed_rate": 281.0, "feed_family": "A"},
        operating_state={"severity": 1.06},
        outputs={"naphtha_rate": 79.0},
    )

    matches = store.similar(
        unit_key="fcc",
        configuration_version="revamp-2025",
        context={
            "regime": "high rate",
            "input.feed_rate": 279.0,
            "input.feed_family": "A",
            "state.severity": 1.04,
        },
    )

    assert len(matches) == 1
    assert matches[0].episode.configuration_version == "revamp-2025"
    assert matches[0].similarity > 0.95


def test_outcome_envelope_is_outcome_oriented(tmp_path: Path):
    store = OperationalEpisodeStore(tmp_path / "episodes.json")
    for day, rate, ron in ((1, 80.0, 94.0), (2, 84.0, 94.4)):
        store.add(
            unit_key="fcc",
            start_time=f"2026-08-0{day}T07:00:00+00:00",
            end_time=f"2026-08-0{day}T11:00:00+00:00",
            kind="stable",
            regime="normal",
            outputs={"naphtha_rate": rate},
            quality={"ron": ron},
        )

    envelope = outcome_envelope(store.list(unit_key="fcc"))
    assert envelope["naphtha_rate"]["mean"] == 82.0
    assert envelope["ron"]["count"] == 2.0
