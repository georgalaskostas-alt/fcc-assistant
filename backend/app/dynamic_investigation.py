"""Adaptive governed investigation: discover, analyze, then autonomously expand evidence."""
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
    MAX_INITIAL_TAGS = 6
    MAX_EXPANSION_TAGS = 6

    def __init__(self, registry: ToolRegistry, planner: InvestigationPlanner | None = None) -> None:
        self.registry, self.runtime = registry, AgentRuntime(registry)
        self.planner = planner or InvestigationPlanner()

    @staticmethod
    def _tag_keys(data: Any, *, limit: int = MAX_INITIAL_TAGS) -> list[str]:
        rows = data if isinstance(data, list) else data.get("hits", data.get("tags", [])) if isinstance(data, dict) else []
        if not isinstance(rows, list): return []
        keys: list[str] = []
        for row in rows:
            if not isinstance(row, dict): continue
            key = row.get("key") or row.get("tag_key") or row.get("name")
            if key and str(key) not in keys: keys.append(str(key))
        return keys[:limit]

    @staticmethod
    def _expansion_queries(goal: str, resolved_tags: list[str]) -> list[str]:
        """Generic evidence-gap queries; never hard-code FCC equipment/tag names."""
        queries = [goal]
        for tag in resolved_tags[:3]:
            queries.extend((tag, f"{tag} related", f"{tag} upstream downstream"))
        return list(dict.fromkeys(q for q in queries if q.strip()))[:8]

    async def _expand_tags(self, *, goal: str, resolved_tags: list[str], context: ToolContext) -> tuple[list[str], list[dict[str, Any]]]:
        """Search semantic/tag registry for additional governed evidence candidates."""
        found: list[str] = []
        traces: list[dict[str, Any]] = []
        for i, query in enumerate(self._expansion_queries(goal, resolved_tags)):
            try:
                result = await self.registry.execute("search_tags", arguments={"query": query}, context=context)
            except Exception as exc:
                traces.append({"query": query, "ok": False, "error": str(exc)})
                continue
            keys = self._tag_keys(result.data, limit=self.MAX_EXPANSION_TAGS)
            traces.append({"query": query, "ok": True, "keys": keys, "provenance": result.provenance})
            for key in keys:
                if key not in resolved_tags and key not in found:
                    found.append(key)
                    if len(found) >= self.MAX_EXPANSION_TAGS:
                        return found, traces
        return found, traces

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
            synthesis["time_window"] = {"start": intent.start_time, "end": intent.end_time, "interpretation": intent.period_interpretation, "site_timezone": intent.site_timezone}
            return DynamicInvestigationResult(discovery=discovery.to_dict(), analysis=None, synthesis=synthesis)

        steps = tuple(AgentStep(id=f"history-{i}", tool_name="get_history",
            arguments={"tag_key": key, "start_time": intent.start_time, "end_time": intent.end_time, "max_count": 2000},
            description=f"Retrieve read-only historian evidence for {key}.") for i,key in enumerate(tag_keys))
        analysis_plan = AgentPlan(goal=f"Historian evidence for: {goal}", steps=steps)
        analysis = await self.runtime.execute(analysis_plan, context=context, stop_on_error=False)
        combined = synthesize_run(analysis).to_dict()
        combined["discovery_evidence"] = discovery_synthesis["evidence_package"]
        archive_execution = discovery.executions.get("search-archive")
        archive_data = archive_execution.result.data if archive_execution and archive_execution.result else None
        archive_rows = archive_data if isinstance(archive_data, list) else archive_data.get("hits", archive_data.get("items", [])) if isinstance(archive_data, dict) else []
        combined["archive_evidence_useful"] = bool(archive_rows)
        archive_limit = None if archive_rows else "Technical archive search executed but returned no usable approved evidence."
        # Adaptive evidence pass: use the governed tag-search tool to discover
        # additional related variables instead of relying on an FCC-specific list.
        expansion_tags, expansion_trace = await self._expand_tags(goal=goal, resolved_tags=tag_keys, context=context)
        combined["adaptive_evidence"] = {
            "attempted": True,
            "search_trace": expansion_trace,
            "additional_tags": expansion_tags,
            "bounded_by": {"max_initial_tags": self.MAX_INITIAL_TAGS, "max_additional_tags": self.MAX_EXPANSION_TAGS},
        }
        if expansion_tags:
            expansion_steps = tuple(AgentStep(
                id=f"expansion-history-{i}", tool_name="get_history",
                arguments={"tag_key": key, "start_time": intent.start_time, "end_time": intent.end_time, "max_count": 2000},
                description=f"Retrieve adaptive read-only historian evidence for {key}.",
            ) for i, key in enumerate(expansion_tags))
            expansion = await self.runtime.execute(AgentPlan(goal=f"Adaptive evidence expansion for: {goal}", steps=expansion_steps), context=context, stop_on_error=False)
            expansion_synthesis = synthesize_run(expansion).to_dict()
            combined["adaptive_evidence"]["run"] = expansion.to_dict()
            combined["evidence_package"] = [*combined.get("evidence_package", []), *expansion_synthesis.get("evidence_package", [])]
            combined["evidence_count"] = len(combined["evidence_package"])
            tag_keys = [*tag_keys, *expansion_tags]
        # Independent event evidence is a separate pass. The tool enforces the
        # authorized unit scope and is read-only.
        event_step = AgentStep(
            id="search-events", tool_name="search_alarms_events",
            arguments={"unit_key": unit_key, "start_time": intent.start_time, "end_time": intent.end_time, "query": goal, "limit": 100},
            description="Search authorized alarms/events for independent event evidence.",
        )
        events_run = await self.runtime.execute(AgentPlan(goal=f"Alarm/event evidence for: {goal}", steps=(event_step,)), context=context, stop_on_error=False)
        events_synthesis = synthesize_run(events_run).to_dict()
        event_execution = events_run.executions.get("search-events")
        event_data = event_execution.result.data if event_execution and event_execution.result else []
        combined["event_evidence"] = {
            "attempted": True,
            "count": len(event_data) if isinstance(event_data, list) else 0,
            "run": events_run.to_dict(),
        }
        combined["evidence_package"] = [*combined.get("evidence_package", []), *events_synthesis.get("evidence_package", [])]
        combined["evidence_count"] = len(combined["evidence_package"])
        # Historical comparison uses only compact measured context, never raw
        # historian payloads, and remains inside the authorized unit.
        episode_context: dict[str, float | str] = {}
        for evidence in combined.get("evidence_package", []):
            if not isinstance(evidence, dict): continue
            description = str(evidence.get("description") or "")
            marker = "historian evidence for "
            lowered = description.casefold()
            if marker not in lowered: continue
            tag = description[lowered.index(marker) + len(marker):].strip().rstrip(".")
            data = evidence.get("data")
            rows = data.get("values", data.get("Values", [])) if isinstance(data, dict) else []
            if isinstance(rows, list) and rows:
                row = rows[-1]
                value = row.get("value", row.get("Value")) if isinstance(row, dict) else row
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    episode_context[f"state.{tag}"] = float(value)
        similar_step = AgentStep(
            id="similar-episodes", tool_name="find_similar_episodes",
            arguments={"context": episode_context, "configuration_version": "current", "limit": 8},
            description="Find comparable historical operating episodes using measured context.",
        )
        similar_run = await self.runtime.execute(AgentPlan(goal=f"Historical comparison for: {goal}", steps=(similar_step,)), context=context, stop_on_error=False)
        similar_synthesis = synthesize_run(similar_run).to_dict()
        similar_execution = similar_run.executions.get("similar-episodes")
        similar_data = similar_execution.result.data if similar_execution and similar_execution.result else []
        combined["similar_episodes"] = {
            "attempted": True,
            "context_features": sorted(episode_context),
            "count": len(similar_data) if isinstance(similar_data, list) else 0,
            "items": similar_data if isinstance(similar_data, list) else [],
            "run": similar_run.to_dict(),
        }
        combined["evidence_package"] = [*combined.get("evidence_package", []), *similar_synthesis.get("evidence_package", [])]
        combined["evidence_count"] = len(combined["evidence_package"])
        combined["resolved_tags"] = tag_keys
        combined["time_window"] = {"start": intent.start_time, "end": intent.end_time, "interpretation": intent.period_interpretation, "site_timezone": intent.site_timezone}
        combined["ready_for_reasoning"] = bool(analysis.evidence)
        synthetic_analysis_warnings = {"Relevant historian tags were not resolved.", "Approved technical-archive evidence was not retrieved."}
        analysis_limits = [item for item in combined.get("limitations", []) if item not in synthetic_analysis_warnings]
        discovery_limits = [item for item in discovery_synthesis.get("limitations", []) if item != "Relevant historian tags were not resolved."]
        if archive_rows:
            discovery_limits = [item for item in discovery_limits if item != "Approved technical-archive evidence was not retrieved."]
        limits = [*analysis_limits, *discovery_limits]
        if archive_limit:
            limits.append(archive_limit)
        combined["limitations"] = list(dict.fromkeys(limits))
        return DynamicInvestigationResult(discovery=discovery.to_dict(), analysis=analysis.to_dict(), synthesis=combined)
