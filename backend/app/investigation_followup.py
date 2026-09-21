"""Bounded follow-up planning for autonomous investigations.

The planner chooses only governed read-only evidence actions. When deterministic
analytics have not produced a hypothesis yet, it performs a bounded goal-level
discovery pass instead of stopping before gathering evidence.
"""
from __future__ import annotations
from typing import Any
from .investigation_value import rank_hypotheses, choose_next_evidence_actions


def _goal_discovery_actions(*, goal: str, unit_key: str, synthesis: dict[str, Any]) -> list[dict[str, Any]]:
    """Bootstrap an investigation without inventing a process hypothesis."""
    actions: list[dict[str, Any]] = []
    time_window = synthesis.get("time_window") if isinstance(synthesis.get("time_window"), dict) else {}
    start_time = time_window.get("start") or time_window.get("start_time")
    end_time = time_window.get("end") or time_window.get("end_time")

    discovered = synthesis.get("discovered_tags") if isinstance(synthesis.get("discovered_tags"), dict) else {}
    discovered_items = discovered.get("items") if isinstance(discovered.get("items"), list) else []

    # First discover real tags from the governed catalog. Once discovery has
    # succeeded, use only those returned keys for historian reads.
    if not discovered_items:
        actions.append({
            "tool": "search_tags",
            "arguments": {"query": goal},
            "purpose": "Discover authorized process measurements relevant to the investigation goal.",
            "expected_evidence": "governed_tag_candidates",
        })
    elif start_time and end_time:
        for row in discovered_items[:2]:
            if not isinstance(row, dict):
                continue
            tag_key = str(row.get("key") or row.get("tag_key") or "").strip()
            if not tag_key:
                continue
            actions.append({
                "tool": "get_history",
                "arguments": {
                    "tag_key": tag_key,
                    "start_time": str(start_time),
                    "end_time": str(end_time),
                    "max_count": 1000,
                },
                "purpose": "Retrieve historian evidence for a governed tag discovered in the previous round.",
                "expected_evidence": "historian_measurements",
            })

    # Independent evidence can be collected immediately when a bounded time
    # window is already known.
    if start_time and end_time:
        actions.append({
            "tool": "search_alarms_events",
            "arguments": {
                "unit_key": unit_key,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "query": goal,
                "limit": 20,
            },
            "purpose": "Check authorized alarms and events in the investigation window.",
            "expected_evidence": "independent_operational_events",
        })

    actions.append({
        "tool": "search_archive",
        "arguments": {
            "query": goal,
            "unit_key": unit_key,
            "limit": 6,
            "approved_only": True,
        },
        "purpose": "Find approved technical context relevant to the investigation goal.",
        "expected_evidence": "approved_technical_context",
    })
    return actions


def plan_follow_up(*, goal: str, unit_key: str, synthesis: dict[str, Any], hypotheses: list[dict[str, Any]], max_actions: int = 3, round_index: int = 0) -> dict[str, Any]:
    ranked = rank_hypotheses(hypotheses)
    selected_hypothesis = ranked[0] if ranked else None
    hypothesis = selected_hypothesis["hypothesis"] if selected_hypothesis else {}
    focus = str(hypothesis.get("statement") or goal)
    query = focus if round_index > 0 else goal
    if hypothesis:
        actions = choose_next_evidence_actions(
            hypothesis=hypothesis,
            synthesis=synthesis,
            unit_key=unit_key,
            query=query,
        )
        # If independent evidence is already present but the relationship is
        # still unresolved, search the governed catalog for measurements named
        # by the evidence gap/focus. This discovers candidates; it never guesses
        # historian keys or embeds FCC-specific variables.
        status = str(hypothesis.get("evidence_status") or "").casefold()
        discovered = synthesis.get("discovered_tags") if isinstance(synthesis.get("discovered_tags"), dict) else {}
        known_keys = {
            str(row.get("key") or row.get("tag_key") or "")
            for row in (discovered.get("items") or [])
            if isinstance(row, dict)
        }
        resolved_keys = {str(value) for value in (synthesis.get("resolved_tags") or [])}
        if status in {
            "specific_independent_evidence_found",
            "relevant_but_insufficient",
            "mixed_independent_evidence",
            "mixed_independent_evidence",
            "contradicting_independent_evidence",
        }:
            actions.append({
                "tool": "search_tags",
                "value": 7,
                "reason": "Discover additional governed measurements relevant to the unresolved evidence gap.",
                "arguments": {"query": focus},
                "exclude_tag_keys": sorted(known_keys | resolved_keys),
            })
        actions = sorted(actions, key=lambda action: -int(action.get("value", 0)))
        planning_mode = "hypothesis_evidence"
    else:
        actions = _goal_discovery_actions(goal=goal, unit_key=unit_key, synthesis=synthesis)
        planning_mode = "goal_discovery"

    selected = actions[:max(0, max_actions)]
    return {
        "needed": bool(selected),
        "actions": selected,
        "focus": focus,
        "planning_mode": planning_mode,
        "selected_hypothesis_id": hypothesis.get("id") if hypothesis else None,
        "selected_hypothesis_score": selected_hypothesis.get("score") if selected_hypothesis else None,
        "hypothesis_ranking": [
            {
                "id": x["hypothesis"].get("id"),
                "score": x["score"],
                "status": x["status"],
                "missing_count": x["missing_count"],
            }
            for x in ranked[:5]
        ],
        "bounded_by": {"max_actions": max_actions, "round_index": round_index},
        "process_control_actions_allowed": False,
    }
