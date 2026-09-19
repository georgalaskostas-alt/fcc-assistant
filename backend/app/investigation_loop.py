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
        plan = plan_follow_up(goal=goal, unit_key=unit_key, synthesis=synthesis, hypotheses=hypotheses, max_actions=3)
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
        rounds.append({"round": round_index + 1, "plan": plan, **result, "new_evidence_count": len(evidence)})
        if not evidence:
            stop_reason = "no_new_evidence"
            break
        synthesis["evidence_package"] = [*synthesis.get("evidence_package", []), *evidence]
        synthesis["evidence_count"] = len(synthesis["evidence_package"])
    return {"rounds": rounds, "rounds_completed": len(rounds), "stop_reason": stop_reason,
            "bounded_by": {"max_rounds": max_rounds, "max_actions_per_round": 3},
            "process_control_actions_allowed": False}
