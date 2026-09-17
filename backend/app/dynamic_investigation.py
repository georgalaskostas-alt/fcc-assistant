"""Dynamic two-pass investigation: discover evidence, then expand into historian analysis."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .agent_runtime import AgentPlan, AgentRuntime, AgentStep
from .agent_tools import ToolContext, ToolRegistry
from .investigation_planner import InvestigationPlanner
from .investigation_synthesis import synthesize_run


@dataclass(frozen=True)
class DynamicInvestigationResult:
    discovery: dict[str, Any]
    analysis: dict[str, Any] | None
    synthesis: dict[str, Any]


class DynamicInvestigator:
    def __init__(self, registry: ToolRegistry, planner: InvestigationPlanner | None = None) -> None:
        self.registry, self.runtime = registry, AgentRuntime(registry)
        self.planner = planner or InvestigationPlanner()

    @staticmethod
    def _tag_keys(data: Any, *, limit: int = 6) -> list[str]:
        rows = data if isinstance(data, list) else data.get("hits", data.get("tags", [])) if isinstance(data, dict) else []
        if not isinstance(rows, list): return []
        keys: list[str] = []
        for row in rows:
            if not isinstance(row, dict): continue
            key = row.get("key") or row.get("tag_key") or row.get("name")
            if key and str(key) not in keys: keys.append(str(key))
        return keys[:limit]

    async def investigate(self, *, goal: str, unit_key: str, context: ToolContext) -> DynamicInvestigationResult:
        intent = self.planner.understand(goal, unit_key=unit_key)
        discovery_plan = self.planner.plan(goal, unit_key=unit_key)
        discovery = await self.runtime.execute(discovery_plan, context=context, stop_on_error=False)
        discovery_synthesis = synthesize_run(discovery).to_dict()
        tag_execution = discovery.executions.get("resolve-tags")
        tag_data = tag_execution.result.data if tag_execution and tag_execution.result else []
        tag_keys = self._tag_keys(tag_data)
        if not tag_keys:
            synthesis = discovery_synthesis
            synthesis["limitations"] = list(dict.fromkeys(synthesis["limitations"] + ["No historian tags were resolved; numerical causal analysis was not attempted."]))
            synthesis["ready_for_reasoning"] = False
            return DynamicInvestigationResult(discovery=discovery.to_dict(), analysis=None, synthesis=synthesis)

        steps = tuple(AgentStep(id=f"history-{i}", tool_name="get_history",
            arguments={"tag_key": key, "start_time": intent.start_time, "end_time": intent.end_time, "max_count": 2000},
            description=f"Retrieve read-only historian evidence for {key}.") for i,key in enumerate(tag_keys))
        analysis_plan = AgentPlan(goal=f"Historian evidence for: {goal}", steps=steps)
        analysis = await self.runtime.execute(analysis_plan, context=context, stop_on_error=False)
        combined = synthesize_run(analysis).to_dict()
        combined["discovery_evidence"] = discovery_synthesis["evidence_package"]
        combined["resolved_tags"] = tag_keys
        combined["time_window"] = {"start": intent.start_time, "end": intent.end_time}
        combined["ready_for_reasoning"] = bool(analysis.evidence)
        # Analysis-only synthesis cannot know that tag/archive discovery already ran.
        # Keep only genuine execution failures from the analysis pass, then merge
        # discovery limitations. This prevents contradictory UI warnings such as
        # "tags were not resolved" while resolved_tags is populated.
        synthetic_analysis_warnings = {
            "Relevant historian tags were not resolved.",
            "Approved technical-archive evidence was not retrieved.",
        }
        analysis_limits = [item for item in combined.get("limitations", []) if item not in synthetic_analysis_warnings]
        combined["limitations"] = list(dict.fromkeys([*discovery_synthesis.get("limitations", []), *analysis_limits]))
        return DynamicInvestigationResult(discovery=discovery.to_dict(), analysis=analysis.to_dict(), synthesis=combined)
