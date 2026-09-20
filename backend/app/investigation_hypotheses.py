"""Machine-checkable hypothesis evaluation for refinery investigations.

This layer ranks evidence gaps, not causal truth. It never manufactures a
mechanism and never authorizes a process-control action.
"""
from __future__ import annotations
from typing import Any
from .evidence_matching import match_hypothesis_evidence


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
    """Describe the evidence boundary; the autonomous loop owns the actual stop reason."""
    autonomous=synthesis.get("autonomous_investigation") if isinstance(synthesis.get("autonomous_investigation"),dict) else {}
    reason=str(autonomous.get("stop_reason") or "evidence_sufficient_for_bounded_assessment")
    unresolved=[h for h in hypotheses if h.get("causal_status")!="established"]
    return {
        "stop": True,
        "reason": reason,
        "reasons": [f"{len(unresolved)} causal hypotheses remain unresolved"] if unresolved else [],
        "iterations_completed": int(autonomous.get("rounds_completed") or 0),
        "next_tools_needed": [],
        "safe_to_assert_causality": False,
    }

def evaluate_hypotheses(*, hypotheses: list[dict[str, Any]], synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach independent evidence availability without turning association into causality."""
    archive = synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"), dict) else {}
    events = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
    similar = synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"), dict) else {}
    archive_items = archive.get("items") if isinstance(archive.get("items"), list) else []
    similar_items = similar.get("items") if isinstance(similar.get("items"), list) else []
    event_count = int(events.get("count") or 0)
    evaluated: list[dict[str, Any]] = []
    for source in hypotheses:
        item = dict(source)
        independent: list[dict[str, Any]] = []
        if archive_items:
            independent.append({"type": "approved_archive", "count": len(archive_items), "status": "available_for_review"})
        if event_count:
            independent.append({"type": "alarms_events", "count": event_count, "status": "available_for_review"})
        if similar_items:
            independent.append({"type": "historical_episodes", "count": len(similar_items), "status": "available_for_comparison"})
        missing: list[str] = []
        if not archive_items: missing.append("Approved technical-archive evidence")
        if not event_count: missing.append("Relevant alarms/events")
        if not similar_items: missing.append("Comparable historical episodes")
        item["independent_evidence"] = independent
        matching = match_hypothesis_evidence(hypothesis=item, synthesis=synthesis)
        item["evidence_matches"] = matching["matches"]
        item["supporting_independent_evidence"] = matching["supporting"]
        item["contradicting_independent_evidence"] = matching["contradicting"]
        item["insufficient_independent_evidence"] = matching["insufficient"]
        item["evidence_match_count"] = matching["match_count"]
        item["evidence_match_status"] = matching["interpretation"]
        item["missing_evidence"] = missing
        if matching["supporting"] and matching["contradicting"]:
            item["evidence_status"] = "mixed_independent_evidence"
        elif matching["contradicting"]:
            item["evidence_status"] = "contradicting_independent_evidence"
        elif matching["supporting"]:
            item["evidence_status"] = "supporting_independent_evidence"
        elif matching["match_count"]:
            item["evidence_status"] = "relevant_but_insufficient"
        else:
            item["evidence_status"] = "independent_evidence_available" if independent else "insufficient_independent_evidence"
        # Availability is not proof. A later evidence matcher must establish that
        # a source explicitly supports or contradicts the mechanism.
        item["causal_status"] = "not_established"
        evaluated.append(item)
    return evaluated
