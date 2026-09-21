"""Value-of-information ranking for bounded investigation follow-up."""
from __future__ import annotations
from typing import Any

_STATUS_WEIGHT = {
    "insufficient_independent_evidence": 6.0,
    "specific_independent_evidence_found": 5.0,
    "relevant_but_insufficient": 5.0,
    "mixed_independent_evidence": 4.5,
    "independent_evidence_available": 4.0,
    "contradicting_independent_evidence": 3.0,
    "supporting_independent_evidence": 2.5,
}

def rank_hypotheses(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for h in hypotheses:
        if not isinstance(h, dict):
            continue
        status = str(h.get("evidence_status") or "")
        if h.get("causal_status") == "established":
            continue
        association = h.get("association") if isinstance(h.get("association"), dict) else {}
        strength = float(association.get("strength") or 0.0)
        missing = len(h.get("missing_evidence") or [])
        contradictions = len(h.get("contradicting_independent_evidence") or [])
        support = len(h.get("supporting_independent_evidence") or [])
        score = _STATUS_WEIGHT.get(status, 1.0) + min(1.0, strength) * 2.0 + min(3, missing) * .6 + contradictions * .35 - support * .15
        ranked.append({"hypothesis": h, "score": round(score, 3), "status": status, "missing_count": missing})
    return sorted(ranked, key=lambda x: (-x["score"], str(x["hypothesis"].get("id") or "")))

def choose_next_evidence_actions(*, hypothesis: dict[str, Any], synthesis: dict[str, Any], unit_key: str, query: str) -> list[dict[str, Any]]:
    archive = synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"), dict) else {}
    events = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
    similar = synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"), dict) else {}
    missing = " ".join(map(str, hypothesis.get("missing_evidence") or [])).casefold()
    status = str(hypothesis.get("evidence_status") or "").casefold()
    actions = []
    if "archive" in missing or "technical" in missing or status in {"relevant_but_insufficient", "specific_independent_evidence_found"} or not archive.get("count"):
        actions.append({"tool": "search_archive", "value": 9, "reason": "Highest-value gap: approved engineering mechanism/context", "arguments": {"query": query, "unit_key": unit_key, "approved_only": True, "limit": 8}})
    if "alarm" in missing or "event" in missing or not events.get("count"):
        actions.append({"tool": "search_alarms_events", "value": 8, "reason": "High-value gap: independent event timing/context", "arguments": {"unit_key": unit_key, "query": query, "limit": 100}})
    if "historical" in missing or "comparable" in missing or not similar.get("count"):
        actions.append({"tool": "find_similar_episodes", "value": 6, "reason": "Need analogical historical comparison", "arguments": {}})
    return sorted(actions, key=lambda a: -int(a["value"]))


def rank_measurement_candidates(*, candidates: list[dict[str, Any]], focus: str,
                                resolved_tags: list[str] | None = None,
                                limit: int = 6) -> list[dict[str, Any]]:
    """Rank governed measurement candidates by explainable information value.

    This is deliberately deterministic. It does not invent process relationships:
    it ranks only metadata returned by the authorized tag catalog.
    """
    resolved = {str(value).casefold() for value in (resolved_tags or [])}
    tokens = {
        token for token in "".join(ch if ch.isalnum() else " " for ch in focus.casefold()).split()
        if len(token) >= 3
    }
    ranked: list[dict[str, Any]] = []
    for index, row in enumerate(candidates):
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or row.get("tag_key") or "").strip()
        if not key or key.casefold() in resolved:
            continue
        fields = [
            key,
            str(row.get("label") or ""),
            str(row.get("name") or ""),
            str(row.get("semantic_key") or row.get("semantic") or ""),
            " ".join(str(value) for value in (row.get("aliases") or [])),
        ]
        haystack = " ".join(fields).casefold()
        matched = sorted(token for token in tokens if token in haystack)
        semantic = str(row.get("semantic_key") or row.get("semantic") or "").strip()
        score = len(matched) * 2.0
        if semantic:
            score += 1.0
        if row.get("unit"):
            score += 0.25
        ranked.append({
            "candidate": row,
            "tag_key": key,
            "score": round(score, 3),
            "matched_focus_tokens": matched,
            "catalog_order": index,
            "reason": "Ranked from governed catalog metadata and investigation focus.",
        })
    ranked.sort(key=lambda item: (-float(item["score"]), int(item["catalog_order"]), str(item["tag_key"])))
    return ranked[:max(0, limit)]


