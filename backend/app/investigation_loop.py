"""Bounded autonomous investigation loop.

Repeatedly reassesses evidence gaps, executes only governed read-only follow-up
actions, and stops on evidence saturation, repeated plans, or the round limit.
"""
from __future__ import annotations
import json
from typing import Any
from .investigation_followup import plan_follow_up
from .investigation_followup_executor import execute_follow_up
from .investigation_reasoning import build_deterministic_analytics
from .investigation_hypotheses import build_hypothesis_candidates, evaluate_hypotheses
from .agent_tools import ToolContext, ToolRegistry
from .investigation_evidence import merge_new_evidence

async def run_autonomous_evidence_loop(*, registry: ToolRegistry, context: ToolContext, goal: str,
                                       unit_key: str, synthesis: dict[str, Any],
                                       time_window: dict[str, Any], episode_context: dict[str, Any],
                                       max_rounds: int = 3) -> dict[str, Any]:
    rounds: list[dict[str, Any]] = []
    seen_plans: set[str] = set()
    stop_reason = "max_rounds_reached"
    for round_index in range(max(0, max_rounds)):
        analytics = build_deterministic_analytics(synthesis)
        hypotheses = evaluate_hypotheses(hypotheses=build_hypothesis_candidates(analytics), synthesis=synthesis)
        plan = plan_follow_up(goal=goal, unit_key=unit_key, synthesis=synthesis, hypotheses=hypotheses, max_actions=3, round_index=round_index)
        if not plan.get("needed"):
            stop_reason = "evidence_saturated"
            break
        fingerprint = json.dumps(plan.get("actions", []), sort_keys=True, default=str)
        if fingerprint in seen_plans:
            stop_reason = "repeated_plan_no_new_direction"
            break
        seen_plans.add(fingerprint)
        result = await execute_follow_up(registry=registry, context=context, goal=goal, plan=plan,
                                         time_window=time_window, episode_context=episode_context)
        evidence = result.get("evidence_package") if isinstance(result.get("evidence_package"), list) else []
        existing = synthesis.get("evidence_package") if isinstance(synthesis.get("evidence_package"), list) else []
        merged, novel = merge_new_evidence(existing, evidence)
        rounds.append({"round": round_index + 1, "plan": plan, **result,
                       "returned_evidence_count": len(evidence), "new_evidence_count": len(novel),
                       "new_evidence_ids": [item.get("stable_evidence_id") for item in novel]})
        if not novel:
            stop_reason = "no_new_evidence"
            break
        synthesis["evidence_package"] = merged
        synthesis["evidence_count"] = len(merged)
        # Preserve the trail of what the autonomous loop learned. The next round
        # can focus on a different unresolved hypothesis rather than blindly
        # repeating the original user wording.
        synthesis["last_autonomous_focus"] = plan.get("focus")
        synthesis["autonomous_rounds_completed"] = round_index + 1
    return {"rounds": rounds, "rounds_completed": len(rounds), "stop_reason": stop_reason,
            "bounded_by": {"max_rounds": max_rounds, "max_actions_per_round": 3},
            "process_control_actions_allowed": False}
