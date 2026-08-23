from pathlib import Path

from app.production_domain import ProductionStore


def test_production_variance_and_attainment(tmp_path: Path):
    store = ProductionStore(tmp_path / "production.json")
    record = store.add(
        scope_kind="unit",
        scope_id="fcc",
        period_start="2026-08-23T00:00:00+00:00",
        period_end="2026-08-24T00:00:00+00:00",
        metric="throughput",
        actual=270.0,
        plan=280.0,
        unit="m3/h",
    )

    assert record.variance == -10.0
    assert round(record.attainment or 0.0, 4) == 0.9643


def test_summary_prioritizes_negative_variances(tmp_path: Path):
    store = ProductionStore(tmp_path / "production.json")
    for metric, actual, plan in (
        ("throughput", 270.0, 280.0),
        ("naphtha", 82.0, 80.0),
        ("lcco", 35.0, 40.0),
    ):
        store.add(
            scope_kind="unit",
            scope_id="fcc",
            period_start="2026-08-23T00:00:00+00:00",
            period_end="2026-08-24T00:00:00+00:00",
            metric=metric,
            actual=actual,
            plan=plan,
            unit="m3/h",
        )

    summary = store.summary(scope_kind="unit", scope_id="fcc")
    losses = summary["negative_variances"]
    assert summary["count"] == 3
    assert [row["metric"] for row in losses] == ["throughput", "lcco"]
