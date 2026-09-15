"""End-to-end autonomous investigation orchestration.

This layer owns goal -> plan -> governed execution -> evidence package. It is
safe to expose to an API because all external actions still pass through the
ToolRegistry and its backend authorization checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_tools import ToolContext, ToolRegistry
from .investigation_planner import InvestigationPlanner
from .investigation_service import InvestigationRunResult, InvestigationService
from .investigation_store import InvestigationStore
from .investigation_synthesis import InvestigationSynthesis, synthesize_run


@dataclass(frozen=True)
class AutonomousInvestigationResult:
    investigation_id: str
    status: str
    plan_id: str
    synthesis: InvestigationSynthesis
    run: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "status": self.status,
            "plan_id": self.plan_id,
            "synthesis": self.synthesis.to_dict(),
            "run": self.run,
        }


class AutonomousInvestigator:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        store: InvestigationStore | None = None,
        planner: InvestigationPlanner | None = None,
    ) -> None:
        self.planner = planner or InvestigationPlanner()
        self.service = InvestigationService(registry=registry, store=store)

    async def investigate(
        self,
        *,
        goal: str,
        user_id: str,
        unit_key: str,
        context: ToolContext,
    ) -> AutonomousInvestigationResult:
        plan = self.planner.plan(goal, unit_key=unit_key)
        result: InvestigationRunResult = await self.service.start(
            goal=goal,
            user_id=user_id,
            unit_key=unit_key,
            plan=plan,
            context=context,
        )
        synthesis = synthesize_run(result.run)
        return AutonomousInvestigationResult(
            investigation_id=result.investigation.id,
            status=result.investigation.status.value,
            plan_id=plan.plan_id,
            synthesis=synthesis,
            run=result.run.to_dict(),
        )
