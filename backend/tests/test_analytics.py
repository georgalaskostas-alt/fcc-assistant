from datetime import datetime, timezone

from app.analytics import NumericPoint, compare_summaries, summarize_pi_payload, summarize_points


def test_summarize_points() -> None:
    points = [
        NumericPoint(datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc), 100.0),
        NumericPoint(datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc), 110.0),
        NumericPoint(datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc), 120.0),
    ]
    summary = summarize_points(points)
    assert summary.count == 3
    assert summary.minimum == 100.0
    assert summary.maximum == 120.0
    assert summary.average == 110.0
    assert summary.absolute_change == 20.0
    assert summary.percent_change == 20.0
    assert summary.duration_hours == 2.0
    assert summary.rate_per_hour == 10.0


def test_summarize_pi_payload() -> None:
    summary = summarize_pi_payload({"Items": [
        {"Timestamp": "2026-08-19T07:00:00Z", "Value": 10.0},
        {"Timestamp": "2026-08-19T15:00:00Z", "Value": 14.0},
    ]})
    assert summary.average == 12.0
    assert summary.absolute_change == 4.0


def test_compare_summaries() -> None:
    reference = summarize_points([
        NumericPoint(datetime(2026, 8, 18, 7, 0, tzinfo=timezone.utc), 100.0),
        NumericPoint(datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc), 100.0),
    ])
    current = summarize_points([
        NumericPoint(datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc), 110.0),
        NumericPoint(datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc), 110.0),
    ])
    comparison = compare_summaries(current, reference)
    assert comparison.average_change == 10.0
    assert comparison.average_change_percent == 10.0
    assert comparison.last_value_change == 10.0
