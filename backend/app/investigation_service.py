"""High-level autonomous refinery investigation service.

Creates durable investigations, executes governed multi-step plans and stores
source-grounded evidence. It is intentionally planner-agnostic: an embedded LLM
or deterministic planner may supply an AgentPlan, while this service owns
execution, persistence and evidence capture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_runtime import AgentPlan, AgentRuntime, AgentRun
from .agent_tools import ToolContext, ToolRegistry
from .investigation_store import EvidenceRecord, Investigation, InvestigationStore
from .investigation_reference import resolve_investigation_reference
from .investigation_continuation import continue_saved_investigation


class InvestigationServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class InvestigationRunResult:
    investigation: Investigation
    run: AgentRun


class InvestigationService:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        store: InvestigationStore | None = None,
    ) -> None:
        self.registry = registry
        self.runtime = AgentRuntime(registry)
        self.store = store or InvestigationStore()

    async def start(
        self,
        *,
        goal: str,
        user_id: str,
        unit_key: str | None,
        plan: AgentPlan,
        context: ToolContext,
        argument_resolver=None,
    ) -> InvestigationRunResult:
        investigation = self.store.create(goal=goal, user_id=user_id, unit_key=unit_key)
        self.store.attach_plan(investigation.id, plan.plan_id)

        run = await self.runtime.execute(
            plan,
            context=context,
            argument_resolver=argument_resolver,
            stop_on_error=False,
        )

        for item in run.evidence:
            result_data = item.get("data") if isinstance(item.get("data"), dict) else {}
            provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
            summary = self._summary(str(item.get("tool") or "tool"), result_data)
            self.store.add_evidence(
                investigation.id,
                EvidenceRecord(
                    source_type="tool",
                    source_id=f"{item.get('tool')}:{item.get('step_id')}",
                    summary=summary,
                    provenance=provenance,
                    payload=result_data,
                ),
            )

        current = self.store.get(investigation.id)
        if current is None:
            raise InvestigationServiceError("Investigation disappeared during execution")
        if run.failed:
            current = self.store.fail(
                investigation.id,
                note="One or more governed tool steps failed; inspect execution evidence.",
            )
        return InvestigationRunResult(investigation=current, run=run)

    def checkpoint(self, investigation_id: str, *, trail: dict[str, Any], synthesis: dict[str, Any]) -> Investigation:
        resume_context = {
            "unit_key": synthesis.get("unit_key"),
            "time_window": synthesis.get("time_window"),
            "resolved_tags": list(synthesis.get("resolved_tags") or []),
            "last_autonomous_focus": synthesis.get("last_autonomous_focus"),
            "autonomous_rounds_completed": synthesis.get("autonomous_rounds_completed", 0),
            "evidence_count": synthesis.get("evidence_count", 0),
        }
        return self.store.save_checkpoint(investigation_id, trail=trail, resume_context=resume_context)

    def resolve_and_resume(self, *, user_id: str, utterance: str, unit_key: str | None = None) -> dict[str, Any]:
        resolved = resolve_investigation_reference(store=self.store, user_id=user_id, utterance=utterance, unit_key=unit_key)
        if resolved["status"] != "resolved":
            return resolved
        investigation_id = str(resolved["investigation"]["id"])
        return {"status": "resolved", "resolution": resolved["investigation"], "resume": self.resume_context(investigation_id)}

    async def continue_from_conversation(self, *, user_id: str, utterance: str, context: ToolContext,
                                         data_source: dict[str, Any], unit_key: str | None = None) -> dict[str, Any]:
        resolved = resolve_investigation_reference(store=self.store, user_id=user_id, utterance=utterance, unit_key=unit_key, context=context)
        if resolved["status"] != "resolved":
            return resolved
        result = await continue_saved_investigation(
            registry=self.registry, store=self.store, investigation_id=str(resolved["investigation"]["id"]),
            context=context, data_source=data_source)
        return {"status": "continued", "resolution": resolved["investigation"], **result}

    def resume_context(self, investigation_id: str) -> dict[str, Any]:
        item = self.store.resume(investigation_id)
        return {
            "investigation_id": item.id,
            "goal": item.goal,
            "unit_key": item.unit_key,
            "trail": dict(item.trail),
            "resume_context": dict(item.resume_context),
            "evidence": [e.payload for e in item.evidence],
        }

    def finish(self, investigation_id: str, *, conclusion: str) -> Investigation:
        if not conclusion.strip():
            raise InvestigationServiceError("Conclusion is required")
        return self.store.complete(investigation_id, conclusion=conclusion)

    @staticmethod
    def _summary(tool_name: str, data: dict[str, Any]) -> str:
        if not data:
            return f"{tool_name} completed without structured result data"
        if "document_id" in data:
            return f"{tool_name}: {data.get('document_id')} rev {data.get('revision', '?')}"
        if "tag" in data:
            tag = data.get("tag")
            if isinstance(tag, dict):
                return f"{tool_name}: {tag.get('name') or tag.get('key') or 'tag'}"
        if "hits" in data and isinstance(data.get("hits"), list):
            return f"{tool_name}: {len(data['hits'])} archive hits"
        return f"{tool_name} returned structured evidence"
