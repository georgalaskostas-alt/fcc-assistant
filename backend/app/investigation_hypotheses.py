"""Machine-checkable hypothesis evaluation for refinery investigations.

This layer ranks evidence gaps, not causal truth. It never manufactures a
mechanism and never authorizes a process-control action.
"""
from __future__ import annotations
from typing import Any


def build_hypothesis_candidates(analytics: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(analytics.get("correlations", [])):
        if not isinstance(item, dict) or item.get("r") is None:
            continue
        left, right = str(item.get("left")), str(item.get("right"))
        r = float(item["r"])
        lagged = item.get("lagged") if isinstance(item.get("lagged"), dict) else {}
        temporal = analytics.get("temporal", {})
        left_t = temporal.get(left, {}) if isinstance(temporal, dict) else {}
        right_t = temporal.get(right, {}) if isinstance(temporal, dict) else {}
        refs = [str(v) for v in (item.get("left_evidence_id"), item.get("right_evidence_id")) if v]
        strength = abs(r)
        status = "candidate_association" if strength >= 0.5 else "weak_association"
        candidates.append({
            "id": f"hypothesis:{index}",
            "type": "evidence_gap_hypothesis",
            "status": status,
            "statement": f"Investigate whether the observed relationship between {left} and {right} has an independent process explanation.",
            "supporting_evidence_ids": refs if strength >= 0.5 else [],
            "contradicting_evidence_ids": [],
            "association": {"pearson_r": r, "strength": strength},
            "temporal_order": {
                "left_onset_index": left_t.get("onset_index"),
                "right_onset_index": right_t.get("onset_index"),
                "best_lag_samples": lagged.get("lag_samples"),
            },
            "missing_evidence": [
                "Independent process/event evidence",
                "Approved technical-archive mechanism or troubleshooting guidance",
                "Relevant alarms/events and operating context",
            ],
            "causal_status": "not_established",
        })
    return candidates


def investigation_stop_decision(*, synthesis: dict[str, Any], analytics: dict[str, Any], hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    adaptive = synthesis.get("adaptive_evidence") if isinstance(synthesis.get("adaptive_evidence"), dict) else {}
    additional = adaptive.get("additional_tags") if isinstance(adaptive.get("additional_tags"), list) else []
    archive_ok = bool(synthesis.get("archive_evidence_useful"))
    event_info = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
    events_attempted = bool(event_info.get("attempted"))
    event_count = int(event_info.get("count") or 0)
    unresolved = [h for h in hypotheses if h.get("causal_status") != "established"]
    reasons: list[str] = []
    if not archive_ok: reasons.append("approved_archive_evidence_missing")
    if unresolved: reasons.append("causal_hypotheses_unresolved")
    if not additional: reasons.append("no_additional_process_variables_resolved")
    if not events_attempted: reasons.append("alarm_event_search_not_attempted")
    elif event_count == 0: reasons.append("no_relevant_alarm_event_evidence")
    return {
        "stop": True,
        "reason": "evidence_boundary_reached",
        "reasons": list(dict.fromkeys(reasons)),
        "iterations_completed": 2 if adaptive.get("attempted") else 1,
        "next_tools_needed": ["search_alarms_events"] if "alarm_event_search_not_attempted" in reasons else [],
        "safe_to_assert_causality": False,
    }
