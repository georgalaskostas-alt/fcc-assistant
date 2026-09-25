"""Adaptive governed investigation: discover, analyze, then autonomously expand evidence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .agent_runtime import AgentPlan, AgentRuntime, AgentStep
from .agent_tools import ToolContext, ToolRegistry
from .investigation_planner import InvestigationPlanner
from .investigation_synthesis import synthesize_run
from .investigation_loop import run_autonomous_evidence_loop


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
    def _match_inherited_tags(goal: str, inherited_tags: list[str]) -> list[str]:
        """Narrow prior governed tags using discriminative semantic-key tokens."""
        import re
        import unicodedata
        from collections import Counter

        def normalize(value: str) -> str:
            decomposed = unicodedata.normalize("NFD", value.casefold())
            value = "".join(
                ch for ch in decomposed
                if unicodedata.category(ch) != "Mn"
            )
            value = value.replace("δp", "dp")
            return re.sub(r"[^a-z0-9α-ω]+", " ", value).strip()

        goal_tokens = set(normalize(goal).split())
        if not goal_tokens or not inherited_tags:
            return []

        token_sets: list[tuple[str, set[str]]] = []
        frequencies: Counter[str] = Counter()

        for tag in inherited_tags:
            tokens = {
                token
                for token in normalize(tag).split()
                if len(token) >= 2
            }
            token_sets.append((tag, tokens))
            frequencies.update(tokens)

        scored: list[tuple[str, float]] = []

        for tag, tokens in token_sets:
            overlap = tokens & goal_tokens
            if not overlap:
                continue

            # Tokens occurring in fewer inherited tags are more informative.
            # Example:
            #   regenerator -> appears in all three tags
            #   dp          -> appears only in regenerator_dp
            score = sum(1.0 / frequencies[token] for token in overlap)
            scored.append((tag, score))

        if not scored:
            return []

        best_score = max(score for _, score in scored)

        return [
            tag
            for tag, score in scored
            if abs(score - best_score) < 1e-12
        ]

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

    async def investigate(
        self,
        *,
        goal: str,
        unit_key: str,
        context: ToolContext,
        previous_context: dict[str, Any] | None = None,
    ) -> DynamicInvestigationResult:
        previous_context = previous_context or {}
        inherited_window = previous_context.get("time_window")
        inherited_tags = [
            str(tag)
            for tag in (previous_context.get("resolved_tags") or [])
            if str(tag).strip()
        ]

        intent = self.planner.understand(
            goal,
            unit_key=unit_key,
            inherited_time_window=inherited_window if isinstance(inherited_window, dict) else None,
        )

        inherited_matches = self._match_inherited_tags(goal, inherited_tags)
        followup_fast_path = bool(
            inherited_window and inherited_tags and inherited_matches
        )

        if followup_fast_path:
            discovery = None
            discovery_synthesis = {
                "goal": goal,
                "evidence_count": 0,
                "findings": [],
                "limitations": [],
                "ready_for_reasoning": False,
                "evidence_package": [],
            }
            discovered_tags: list[str] = []
            tag_keys = inherited_matches[:self.MAX_INITIAL_TAGS]
        else:
            discovery_plan = self.planner.plan(goal, unit_key=unit_key)
            discovery = await self.runtime.execute(
                discovery_plan,
                context=context,
                stop_on_error=False,
            )
            discovery_synthesis = synthesize_run(discovery).to_dict()
            tag_execution = discovery.executions.get("resolve-tags")
            tag_data = (
                tag_execution.result.data
                if tag_execution and tag_execution.result
                else []
            )
            discovered_tags = self._tag_keys(tag_data)
            tag_keys = (
                discovered_tags
                or inherited_matches
                or inherited_tags[:self.MAX_INITIAL_TAGS]
            )
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
        archive_execution = (
            discovery.executions.get("search-archive")
            if discovery is not None
            else None
        )
        archive_data = (
            archive_execution.result.data
            if archive_execution and archive_execution.result
            else None
        )
        archive_rows = (
            archive_data
            if isinstance(archive_data, list)
            else archive_data.get("hits", archive_data.get("items", []))
            if isinstance(archive_data, dict)
            else []
        )
        combined["archive_evidence_useful"] = bool(archive_rows)
        combined["archive_evidence"] = {
            "attempted": True,
            "count": len(archive_rows),
            "items": archive_rows[:8],
            "approved_only": True,
        }
        # Pull controlled metadata for the strongest archive hits so later
        # reasoning can cite exact document/revision/source rather than merely
        # knowing that a search succeeded.
        archive_contexts: list[dict[str, Any]] = []
        for index, row in enumerate(archive_rows[:4]):
            record_id = row.get("record_id") if isinstance(row, dict) else None
            if not record_id: continue
            try:
                context_result = await self.registry.execute("get_document_context", arguments={"record_id": str(record_id)}, context=context)
                archive_contexts.append({"record_id": record_id, "context": context_result.data, "provenance": context_result.provenance})
            except Exception as exc:
                archive_contexts.append({"record_id": record_id, "error": str(exc)})
        combined["archive_evidence"]["document_contexts"] = archive_contexts
        archive_limit = (
            None
            if followup_fast_path or archive_rows
            else "Technical archive search executed but returned no usable approved evidence."
        )
        # A focused inherited follow-up already has a governed evidence scope.
        # Do not launch adaptive discovery for that descriptive query.
        if followup_fast_path:
            expansion_tags, expansion_trace = [], []
        else:
            expansion_tags, expansion_trace = await self._expand_tags(
                goal=goal,
                resolved_tags=tag_keys,
                context=context,
            )
        combined["adaptive_evidence"] = {
            "attempted": not followup_fast_path,
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
            if not isinstance(evidence, dict) or evidence.get("tool") != "get_history":
                continue
            data = evidence.get("data")
            if not isinstance(data, dict):
                continue
            tag_meta = data.get("tag") if isinstance(data.get("tag"), dict) else {}
            tag = str(tag_meta.get("key") or data.get("tag_key") or "").strip()
            if not tag:
                description = str(evidence.get("description") or "")
                marker = "historian evidence for "
                lowered = description.casefold()
                if marker in lowered:
                    tag = description[lowered.index(marker) + len(marker):].strip().rstrip(".")
            payload = data.get("data", data)
            rows = payload if isinstance(payload, list) else next(
                (payload.get(key) for key in ("values", "Values", "items", "Items")
                 if isinstance(payload, dict) and isinstance(payload.get(key), list)),
                [],
            )
            if isinstance(rows, list) and rows and tag:
                row = rows[-1]
                value = row.get("value", row.get("Value")) if isinstance(row, dict) else row
                if isinstance(value, dict):
                    value = value.get("Value", value.get("value"))
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
        # Bounded autonomous evidence loop: reassess, search, merge, and stop safely.
        combined["resolved_tags"] = tag_keys
        combined["unit_key"] = unit_key
        combined["context_inherited"] = bool(
            (not discovered_tags and inherited_tags)
            or (
                inherited_window
                and intent.period_interpretation
                == (
                    inherited_window.get("interpretation")
                    if isinstance(inherited_window, dict)
                    else None
                )
            )
        )

        if followup_fast_path:
            combined["autonomous_investigation"] = {
                "attempted": False,
                "reason": "bounded_inherited_followup",
            }
        else:
            combined["autonomous_investigation"] = await run_autonomous_evidence_loop(
                registry=self.registry,
                context=context,
                goal=goal,
                unit_key=unit_key,
                synthesis=combined,
                time_window={
                    "start": intent.start_time,
                    "end": intent.end_time,
                },
                episode_context=episode_context,
                max_rounds=3,
            )
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
        combined["followup_fast_path"] = followup_fast_path
        return DynamicInvestigationResult(
            discovery=discovery.to_dict() if discovery is not None else {
                "goal": goal,
                "steps": [],
                "executions": {},
                "evidence": [],
            },
            analysis=analysis.to_dict(),
            synthesis=combined,
        )
