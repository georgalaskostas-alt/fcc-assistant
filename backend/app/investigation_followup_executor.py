"""Execute a small, governed second investigation round.

Only read-only evidence tools are accepted. The caller supplies already bounded
follow-up actions; this executor adds the investigation time window where needed.
"""
from __future__ import annotations
from typing import Any
from .agent_runtime import AgentPlan, AgentRuntime, AgentStep
from .agent_tools import ToolContext, ToolRegistry, ToolEffect
from .investigation_synthesis import synthesize_run

async def execute_follow_up(*, registry: ToolRegistry, context: ToolContext, goal: str,
                            plan: dict[str, Any], time_window: dict[str, Any],
                            episode_context: dict[str, Any]) -> dict[str, Any]:
    steps: list[AgentStep] = []
    for index, action in enumerate(plan.get("actions", [])[:3]):
        if not isinstance(action, dict): continue
        tool = str(action.get("tool") or "")
        definition = registry.get_definition(tool)
        if definition is None or definition.effect != ToolEffect.READ_ONLY:
            continue
        args = dict(action.get("arguments") or {})
        if tool == "search_alarms_events":
            args.setdefault("start_time", str(time_window.get("start") or ""))
            args.setdefault("end_time", str(time_window.get("end") or ""))
        elif tool == "find_similar_episodes":
            args.setdefault("context", episode_context)
            args.setdefault("configuration_version", "current")
            args.setdefault("limit", 8)
        steps.append(AgentStep(id=f"follow-up-{index}", tool_name=tool, arguments=args,
                               description=str(action.get("reason") or "Autonomous evidence follow-up.")))
    if not steps:
        return {"attempted": False, "evidence_package": [], "run": None}
    run = await AgentRuntime(registry).execute(AgentPlan(goal=f"Autonomous follow-up for: {goal}", steps=tuple(steps)),
                                               context=context, stop_on_error=False)
    synthesis = synthesize_run(run).to_dict()
    return {"attempted": True, "evidence_package": synthesis.get("evidence_package", []),
            "limitations": synthesis.get("limitations", []), "run": run.to_dict()}
