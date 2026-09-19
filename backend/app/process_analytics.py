"""Deterministic read-only analytics for historian evidence."""
from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool): return None
    if isinstance(value, (int, float)): return float(value)
    try: return float(value)
    except (TypeError, ValueError): return None


def _rows(payload: Any) -> list[Any]:
    """Accept canonical, PI-style and simulator-style historian envelopes."""
    current = payload
    for _ in range(3):
        if not isinstance(current, dict): break
        nested = current.get("data")
        if isinstance(nested, (dict, list)):
            current = nested
            continue
        break
    if isinstance(current, list): return current
    if not isinstance(current, dict): return []
    for key in ("values", "Values", "items", "Items"):
        rows = current.get(key)
        if isinstance(rows, list): return rows
    return []


def extract_series(payload: Any) -> list[float]:
    result: list[float] = []
    for row in _rows(payload):
        if isinstance(row, dict):
            value = row.get("value", row.get("Value"))
            if isinstance(value, dict): value = value.get("Value", value.get("value"))
        else:
            value = row
        numeric = _number(value)
        if numeric is not None: result.append(numeric)
    return result


def summarize_series(payload: Any) -> dict[str, Any]:
    values = extract_series(payload)
    if not values: return {"count": 0, "available": False}
    avg = mean(values); sd = pstdev(values) if len(values) > 1 else 0.0
    return {"count": len(values), "available": True, "min": min(values), "max": max(values), "mean": avg,
            "stdev": sd, "first": values[0], "last": values[-1], "delta": values[-1]-values[0], "range": max(values)-min(values)}


def pearson(left_payload: Any, right_payload: Any) -> dict[str, Any]:
    """Return one canonical coefficient plus the legacy key during migration.

    `r` is the application contract used by structured claims. `pearson_r` is
    retained temporarily so older consumers do not break while the refinery
    analytics contract converges.
    """
    left, right = extract_series(left_payload), extract_series(right_payload); n = min(len(left), len(right))
    if n < 3: return {"available": False, "count": n, "reason": "At least three aligned samples are required"}
    left, right = left[:n], right[:n]; ml, mr = mean(left), mean(right)
    numerator = sum((a-ml)*(b-mr) for a,b in zip(left,right)); dl = sqrt(sum((a-ml)**2 for a in left)); dr = sqrt(sum((b-mr)**2 for b in right))
    if dl == 0 or dr == 0: return {"available": False, "count": n, "reason": "Constant series cannot be correlated"}
    coefficient = numerator/(dl*dr)
    return {"available": True, "count": n, "r": coefficient, "pearson_r": coefficient, "warning": "Correlation is association, not proof of causation."}


def detect_deviation(payload: Any, *, sigma: float = 3.0) -> dict[str, Any]:
    values = extract_series(payload)
    if len(values) < 5: return {"available": False, "count": len(values), "reason": "Insufficient samples"}
    avg, sd = mean(values), pstdev(values)
    if sd == 0: return {"available": True, "count": len(values), "deviations": [], "mean": avg, "stdev": sd}
    deviations = [{"index": i, "value": value, "z_score": (value-avg)/sd} for i,value in enumerate(values) if abs((value-avg)/sd) >= sigma]
    return {"available": True, "count": len(values), "mean": avg, "stdev": sd, "sigma": sigma, "deviations": deviations}


def temporal_profile(payload: Any) -> dict[str, Any]:
    """Describe onset/change behavior without asserting causation."""
    values = extract_series(payload)
    n = len(values)
    if n < 8:
        return {"available": False, "count": n, "reason": "At least eight samples are required"}
    q = max(2, n // 4)
    early, late = values[:q], values[-q:]
    early_mean, late_mean = mean(early), mean(late)
    net = late_mean - early_mean
    increments = [values[i] - values[i - 1] for i in range(1, n)]
    max_rise_index = max(range(1, n), key=lambda i: increments[i - 1])
    max_fall_index = min(range(1, n), key=lambda i: increments[i - 1])
    total_range = max(values) - min(values)
    threshold = max(total_range * 0.15, pstdev(values) * 0.5)
    baseline = early_mean
    onset_index = next((i for i, value in enumerate(values[q:], start=q) if abs(value - baseline) >= threshold), None)
    direction = "increasing" if net > 0 else "decreasing" if net < 0 else "stable"
    return {
        "available": True, "count": n, "early_mean": early_mean, "late_mean": late_mean,
        "change": net, "direction": direction, "onset_index": onset_index,
        "max_rise_index": max_rise_index, "max_rise_step": increments[max_rise_index - 1],
        "max_fall_index": max_fall_index, "max_fall_step": increments[max_fall_index - 1],
    }


def lagged_pearson(left_payload: Any, right_payload: Any, *, max_lag: int = 12) -> dict[str, Any]:
    """Find strongest sample-lag association; lag is descriptive, not causal."""
    left, right = extract_series(left_payload), extract_series(right_payload)
    n = min(len(left), len(right))
    if n < 8:
        return {"available": False, "count": n, "reason": "At least eight aligned samples are required"}
    left, right = left[:n], right[:n]
    bound = min(max_lag, max(1, n // 4))
    candidates: list[dict[str, Any]] = []
    for lag in range(-bound, bound + 1):
        if lag < 0: a, b = left[-lag:], right[:n + lag]
        elif lag > 0: a, b = left[:n - lag], right[lag:]
        else: a, b = left, right
        result = pearson(a, b)
        if result.get("available"):
            candidates.append({"lag_samples": lag, "r": result["r"], "count": result["count"]})
    if not candidates:
        return {"available": False, "count": n, "reason": "No valid lagged association"}
    strongest = max(candidates, key=lambda item: abs(float(item["r"])))
    return {**strongest, "available": True, "warning": "Lagged association and temporal ordering do not establish causation."}
