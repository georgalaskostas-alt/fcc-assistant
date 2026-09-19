"""Bounded follow-up planning for autonomous investigations.

The planner chooses only governed read-only evidence actions and never process
control actions. It turns explicit evidence gaps into a small next-search plan.
"""
from __future__ import annotations
from typing import Any

def plan_follow_up(*, goal: str, unit_key: str, synthesis: dict[str, Any], hypotheses: list[dict[str, Any]], max_actions: int = 3, round_index: int = 0) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    statuses = {str(h.get("evidence_status") or "") for h in hypotheses if isinstance(h, dict)}
    archive = synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"), dict) else {}
    events = synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"), dict) else {}
    similar = synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"), dict) else {}

    unresolved = [h for h in hypotheses if isinstance(h, dict) and h.get("evidence_status") in {"independent_evidence_available","relevant_but_insufficient","insufficient_independent_evidence","mixed_independent_evidence"}]
    focus = str(unresolved[0].get("statement") or goal) if unresolved else goal
    query = focus if round_index > 0 else goal
    if not archive.get("count") or unresolved:
        actions.append({"tool":"search_archive","reason":"Need evidence for the unresolved hypothesis","arguments":{"query":query,"unit_key":unit_key,"approved_only":True,"limit":8}})
    if not events.get("count"):
        actions.append({"tool":"search_alarms_events","reason":"Need independent event evidence","arguments":{"unit_key":unit_key,"query":query,"limit":100}})
    if not similar.get("count"):
        actions.append({"tool":"find_similar_episodes","reason":"Need historical comparison evidence","arguments":{}})

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        if action["tool"] in seen: continue
        seen.add(action["tool"]); unique.append(action)
    selected = unique[:max(0, max_actions)]
    return {
        "needed": bool(selected),
        "actions": selected,
        "focus": query,
        "bounded_by": {"max_actions": max_actions, "round_index": round_index},
        "process_control_actions_allowed": False,
    }
