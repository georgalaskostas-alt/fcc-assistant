from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import mean
from typing import Any


class AnalyticsError(RuntimeError):
    pass


@dataclass(frozen=True)
class NumericPoint:
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class SeriesSummary:
    count: int
    minimum: float
    maximum: float
    average: float
    first: float
    last: float
    absolute_change: float
    percent_change: float | None
    standard_deviation: float
    duration_hours: float
    rate_per_hour: float | None


@dataclass(frozen=True)
class PeriodComparison:
    average_change: float
    average_change_percent: float | None
    minimum_change: float
    maximum_change: float
    last_value_change: float
    last_value_change_percent: float | None


def _parse_timestamp(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise AnalyticsError("PI point timestamp is missing or invalid")

    normalized = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AnalyticsError(f"Invalid PI timestamp: {raw}") from exc


def _extract_numeric_value(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        nested = raw.get("Value")
        if isinstance(nested, bool):
            return None
        if isinstance(nested, (int, float)):
            return float(nested)
    return None


def points_from_pi_payload(payload: dict[str, Any]) -> list[NumericPoint]:
    items = payload.get("Items")
    if not isinstance(items, list):
        raise AnalyticsError("PI response does not contain an Items list")

    points: list[NumericPoint] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = _extract_numeric_value(item.get("Value"))
        if value is None:
            continue
        timestamp = _parse_timestamp(item.get("Timestamp"))
        points.append(NumericPoint(timestamp=timestamp, value=value))

    points.sort(key=lambda point: point.timestamp)
    if not points:
        raise AnalyticsError("No numeric PI values were available for analysis")
    return points


def _percent_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return ((new - old) / abs(old)) * 100.0


def summarize_points(points: list[NumericPoint]) -> SeriesSummary:
    if not points:
        raise AnalyticsError("Cannot summarize an empty series")

    values = [point.value for point in points]
    avg = mean(values)
    variance = mean([(value - avg) ** 2 for value in values])
    standard_deviation = sqrt(variance)
    first = values[0]
    last = values[-1]
    absolute_change = last - first
    duration_seconds = (points[-1].timestamp - points[0].timestamp).total_seconds()
    duration_hours = max(duration_seconds / 3600.0, 0.0)

    return SeriesSummary(
        count=len(values),
        minimum=min(values),
        maximum=max(values),
        average=avg,
        first=first,
        last=last,
        absolute_change=absolute_change,
        percent_change=_percent_change(first, last),
        standard_deviation=standard_deviation,
        duration_hours=duration_hours,
        rate_per_hour=(absolute_change / duration_hours if duration_hours > 0 else None),
    )


def summarize_pi_payload(payload: dict[str, Any]) -> SeriesSummary:
    return summarize_points(points_from_pi_payload(payload))


def compare_summaries(current: SeriesSummary, reference: SeriesSummary) -> PeriodComparison:
    return PeriodComparison(
        average_change=current.average - reference.average,
        average_change_percent=_percent_change(reference.average, current.average),
        minimum_change=current.minimum - reference.minimum,
        maximum_change=current.maximum - reference.maximum,
        last_value_change=current.last - reference.last,
        last_value_change_percent=_percent_change(reference.last, current.last),
    )
