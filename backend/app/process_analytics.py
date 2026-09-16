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
    # Tool adapters may wrap the historian response in one or more `data` envelopes.
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
            # PI values can themselves be objects; only numeric scalar values belong in analytics.
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
    left, right = extract_series(left_payload), extract_series(right_payload); n = min(len(left), len(right))
    if n < 3: return {"available": False, "count": n, "reason": "At least three aligned samples are required"}
    left, right = left[:n], right[:n]; ml, mr = mean(left), mean(right)
    numerator = sum((a-ml)*(b-mr) for a,b in zip(left,right)); dl = sqrt(sum((a-ml)**2 for a in left)); dr = sqrt(sum((b-mr)**2 for b in right))
    if dl == 0 or dr == 0: return {"available": False, "count": n, "reason": "Constant series cannot be correlated"}
    return {"available": True, "count": n, "pearson_r": numerator/(dl*dr), "warning": "Correlation is association, not proof of causation."}


def detect_deviation(payload: Any, *, sigma: float = 3.0) -> dict[str, Any]:
    values = extract_series(payload)
    if len(values) < 5: return {"available": False, "count": len(values), "reason": "Insufficient samples"}
    avg, sd = mean(values), pstdev(values)
    if sd == 0: return {"available": True, "count": len(values), "deviations": [], "mean": avg, "stdev": sd}
    deviations = [{"index": i, "value": value, "z_score": (value-avg)/sd} for i,value in enumerate(values) if abs((value-avg)/sd) >= sigma]
    return {"available": True, "count": len(values), "mean": avg, "stdev": sd, "sigma": sigma, "deviations": deviations}
