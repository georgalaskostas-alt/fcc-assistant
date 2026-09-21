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
from .investigation_reconciliation import reconcile_follow_up
from .investigation_budget import InvestigationBudget
from .investigation_stop import classify_execution_boundary, normalize_stop_reason
from .investigation_value import score_evidence_gain, evolve_hypothesis_branches
from .semantic_engineering_graph import build_semantic_engineering_graph, traverse_semantic_neighbors, trace_process_paths
from .investigation_graph_planner import semantic_discovery_candidates, semantic_candidates_to_actions, process_path_candidates
from .site_model import load_site_model

async def run_autonomous_evidence_loop(*, registry: ToolRegistry, context: ToolContext, goal: str,
                                       unit_key: str, synthesis: dict[str, Any],
                                       time_window: dict[str, Any], episode_context: dict[str, Any],
                                       max_rounds: int = 3, max_total_tool_calls: int = 7) -> dict[str, Any]:
    budget = InvestigationBudget(max_rounds=max_rounds, max_actions_per_round=3, max_total_tool_calls=max_total_tool_calls)
    # Make the caller-resolved window available to every planning round. This keeps
    # discovery and historian reads on the same explicit bounded interval.
    synthesis.setdefault("time_window", dict(time_window))
    rounds: list[dict[str, Any]] = []
    seen_plans: set[str] = set()
    stop_reason = "max_rounds_reached"
    for round_index in range(max(0, max_rounds)):
        if budget.remaining_tool_calls <= 0:
            stop_reason = "tool_budget_exhausted"
            break
        analytics = build_deterministic_analytics(synthesis)
        hypotheses = evaluate_hypotheses(hypotheses=build_hypothesis_candidates(analytics), synthesis=synthesis)
        branch_lifecycle = evolve_hypothesis_branches(
            hypotheses=hypotheses,
            previous_branches=synthesis.get("hypothesis_branch_lifecycle") if isinstance(synthesis.get("hypothesis_branch_lifecycle"), list) else [],
        )
        synthesis["hypothesis_branch_lifecycle"] = branch_lifecycle
        active_branch_ids = {
            str(item.get("branch_id")) for item in branch_lifecycle
            if item.get("state") != "prune"
        }
        active_hypotheses = [
            item for item in hypotheses
            if str(item.get("id") or "") in active_branch_ids
        ] if branch_lifecycle else hypotheses
        synthesis["investigation_focus"] = str(active_hypotheses[0].get("statement") or goal) if active_hypotheses else goal
        plan = plan_follow_up(goal=goal, unit_key=unit_key, synthesis=synthesis, hypotheses=active_hypotheses, max_actions=3, round_index=round_index)
        # Use the refinery semantic graph as a bounded second source of planning
        # context. It may discover measurements/equipment, but never creates
        # process-control actions or asserts causality.
        evidence_graph = synthesis.get("evidence_graph") if isinstance(synthesis.get("evidence_graph"), dict) else {"nodes":[],"edges":[]}
        semantic_graph = build_semantic_engineering_graph(unit_key=unit_key, site=load_site_model(), hypotheses=active_hypotheses, evidence_graph=evidence_graph)
        neighborhood = traverse_semantic_neighbors(graph=semantic_graph, start_ids=[str(h.get("id")) for h in active_hypotheses if h.get("id")], max_depth=3, max_nodes=32)
        graph_candidates = semantic_discovery_candidates(neighborhood=neighborhood, synthesis=synthesis, limit=4)
        node_by_id={str(n.get("id")):n for n in semantic_graph.get("nodes",[]) if isinstance(n,dict)}
        path_start_ids=[]
        for path in neighborhood.get("paths",[]):
            if not isinstance(path,dict):continue
            for node_id in (path.get("from"),path.get("to")):
                node=node_by_id.get(str(node_id),{})
                if node.get("kind") in {"equipment","stream"} and str(node_id) not in path_start_ids:path_start_ids.append(str(node_id))
        process_paths=trace_process_paths(graph=semantic_graph,start_ids=path_start_ids[:6],max_depth=4,max_paths=24)
        path_candidates=process_path_candidates(process_paths=process_paths,graph=semantic_graph,synthesis=synthesis,limit=4)
        combined_candidates=[];candidate_seen=set()
        for candidate in [*path_candidates,*graph_candidates]:
            fp=(candidate.get("kind"),candidate.get("tag_key") or candidate.get("equipment_key"))
            if fp in candidate_seen:continue
            candidate_seen.add(fp);combined_candidates.append(candidate)
        graph_candidates=combined_candidates[:6]
        synthesis["semantic_discovery"] = {"neighborhood":neighborhood,"process_paths":process_paths,"candidates":graph_candidates}
        if graph_candidates and plan.get("planning_mode") != "new_measurement_history":
            existing=list(plan.get("actions") or [])
            fingerprints={(a.get("tool"),str((a.get("arguments") or {}).get("query") or ""),str((a.get("arguments") or {}).get("equipment_key") or "")) for a in existing if isinstance(a,dict)}
            for action in semantic_candidates_to_actions(candidates=graph_candidates,unit_key=unit_key):
                fp=(action.get("tool"),str((action.get("arguments") or {}).get("query") or ""),str((action.get("arguments") or {}).get("equipment_key") or ""))
                if fp not in fingerprints:
                    existing.append(action);fingerprints.add(fp)
            existing.sort(key=lambda a:-int(a.get("value",0)))
            plan["actions"]=existing[:3];plan["needed"]=bool(plan["actions"])
            if plan["actions"]:plan["planning_mode"]="process_path_discovery" if path_candidates else "semantic_graph_discovery"
            plan["semantic_candidates"]=graph_candidates
        if not plan.get("needed"):
            # No actionable governed follow-up is not, by itself, proof that evidence is sufficient.
            has_evidence = bool(synthesis.get("evidence") or synthesis.get("executions") or synthesis.get("history"))
            stop_reason = "evidence_saturated" if hypotheses and has_evidence else "no_new_evidence"
            break
        fingerprint = json.dumps(plan.get("actions", []), sort_keys=True, default=str)
        if fingerprint in seen_plans:
            stop_reason = "repeated_plan_no_new_direction"
            break
        seen_plans.add(fingerprint)
        requested_actions = len(plan.get("actions") or [])
        allowed_actions = budget.allowance(requested_actions)
        if allowed_actions <= 0:
            stop_reason = "tool_budget_exhausted"
            break
        bounded_plan = dict(plan)
        bounded_plan["actions"] = list(plan.get("actions") or [])[:allowed_actions]
        result = await execute_follow_up(registry=registry, context=context, goal=goal, plan=bounded_plan,
                                         time_window=time_window, episode_context=episode_context)
        executed = len((result.get("run") or {}).get("executions") or []) if isinstance(result.get("run"), dict) else 0
        budget.record(round_number=round_index + 1, requested=requested_actions, executed=executed)
        plan = bounded_plan
        boundary = classify_execution_boundary(result)
        evidence = result.get("evidence_package") if isinstance(result.get("evidence_package"), list) else []
        existing = synthesis.get("evidence_package") if isinstance(synthesis.get("evidence_package"), list) else []
        merged, novel = merge_new_evidence(existing, evidence)
        rounds.append({"round": round_index + 1, "plan": plan, **result,
                       "hypothesis_branch_lifecycle": branch_lifecycle,
                       "returned_evidence_count": len(evidence), "new_evidence_count": len(novel),
                       "new_evidence_ids": [item.get("stable_evidence_id") for item in novel]})
        if boundary:
            stop_reason = boundary
            break
        if not novel:
            stop_reason = "no_new_evidence"
            break
        synthesis["evidence_package"] = merged
        synthesis["evidence_count"] = len(merged)
        reconciliation = reconcile_follow_up(synthesis, result)
        rounds[-1]["reconciliation"] = reconciliation
        after_analytics = build_deterministic_analytics(synthesis)
        historian_actions = [
            action for action in plan.get("actions", [])
            if isinstance(action, dict) and action.get("tool") == "get_history"
        ]
        realized_gain = [
            score_evidence_gain(
                before_analytics=analytics,
                after_analytics=after_analytics,
                tag_key=str((action.get("arguments") or {}).get("tag_key") or ""),
            )
            for action in historian_actions
            if str((action.get("arguments") or {}).get("tag_key") or "")
        ]
        if realized_gain:
            rounds[-1]["realized_information_gain"] = realized_gain
            synthesis["measurement_information_gain"] = [
                *(synthesis.get("measurement_information_gain") or []),
                *realized_gain,
            ]
        next_hypotheses = evaluate_hypotheses(
            hypotheses=build_hypothesis_candidates(after_analytics),
            synthesis=synthesis,
        )
        next_lifecycle = evolve_hypothesis_branches(
            hypotheses=next_hypotheses,
            previous_branches=branch_lifecycle,
        )
        rounds[-1]["branch_lifecycle_after_evidence"] = next_lifecycle
        synthesis["hypothesis_branch_lifecycle"] = next_lifecycle
        # Recompute hypotheses on the next iteration from the newly reconciled
        # archive/event/history state, so the planner can change direction.
        # Preserve the trail of what the autonomous loop learned. The next round
        # can focus on a different unresolved hypothesis rather than blindly
        # repeating the original user wording.
        synthesis["last_autonomous_focus"] = plan.get("focus")
        synthesis["autonomous_rounds_completed"] = round_index + 1
    stop_reason = normalize_stop_reason(stop_reason)
    return {"rounds": rounds, "rounds_completed": len(rounds), "stop_reason": stop_reason,
            "bounded_by": {"max_rounds": max_rounds, "max_actions_per_round": 3, "max_total_tool_calls": max_total_tool_calls},
            "budget": budget.to_dict(),
            "process_control_actions_allowed": False}
