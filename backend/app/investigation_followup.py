"""Bounded follow-up planning for autonomous investigations.

The planner chooses only governed read-only evidence actions and never process
control actions. It turns explicit evidence gaps into a small next-search plan.
"""
from __future__ import annotations
from typing import Any
from .investigation_value import rank_hypotheses, choose_next_evidence_actions

def plan_follow_up(*, goal: str, unit_key: str, synthesis: dict[str, Any], hypotheses: list[dict[str, Any]], max_actions: int = 3, round_index: int = 0) -> dict[str, Any]:
    ranked = rank_hypotheses(hypotheses)
    selected_hypothesis = ranked[0] if ranked else None
    hypothesis = selected_hypothesis["hypothesis"] if selected_hypothesis else {}
    focus = str(hypothesis.get("statement") or goal)
    query = focus if round_index > 0 else goal
    actions = choose_next_evidence_actions(
        hypothesis=hypothesis,
        synthesis=synthesis,
        unit_key=unit_key,
        query=query,
    ) if hypothesis else []
    selected = actions[:max(0, max_actions)]
    return {
        "needed": bool(selected),
        "actions": selected,
        "focus": focus,
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
