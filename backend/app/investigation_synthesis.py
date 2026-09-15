"""Evidence synthesis primitives for autonomous refinery investigations.

No operational conclusion is invented when evidence is absent. This module
creates a structured evidence package that a local reasoning model can consume
and exposes explicit confidence/limitations for the UI and reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent_runtime import AgentRun, StepStatus


@dataclass(frozen=True)
class InvestigationFinding:
    statement: str
    evidence_refs: tuple[str, ...]
    confidence: str = "low"


@dataclass(frozen=True)
class InvestigationSynthesis:
    goal: str
    evidence_count: int
    findings: tuple[InvestigationFinding, ...] = ()
    limitations: tuple[str, ...] = ()
    ready_for_reasoning: bool = False
    evidence_package: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "evidence_count": self.evidence_count,
            "findings": [
                {"statement": f.statement, "evidence_refs": list(f.evidence_refs), "confidence": f.confidence}
                for f in self.findings
            ],
            "limitations": list(self.limitations),
            "ready_for_reasoning": self.ready_for_reasoning,
            "evidence_package": list(self.evidence_package),
        }


def synthesize_run(run: AgentRun) -> InvestigationSynthesis:
    package: list[dict[str, Any]] = []
    limitations: list[str] = []
    successful_tools: set[str] = set()

    for step_id, execution in run.executions.items():
        if execution.status == StepStatus.SUCCEEDED and execution.result is not None:
            successful_tools.add(execution.step.tool_name)
            package.append({
                "evidence_id": f"{execution.step.tool_name}:{step_id}",
                "tool": execution.step.tool_name,
                "description": execution.step.description,
                "data": execution.result.data,
                "provenance": execution.result.provenance,
            })
        elif execution.status in {StepStatus.FAILED, StepStatus.SKIPPED}:
            limitations.append(f"{step_id}: {execution.error or execution.status.value}")

    if "search_tags" not in successful_tools:
        limitations.append("Relevant historian tags were not resolved.")
    if "search_archive" not in successful_tools:
        limitations.append("Approved technical-archive evidence was not retrieved.")

    # Do not manufacture a causal finding here. Causal synthesis belongs to the
    # reasoning layer and must cite evidence IDs from this package.
    ready = bool(package) and "search_tags" in successful_tools
    return InvestigationSynthesis(
        goal=run.plan.goal,
        evidence_count=len(package),
        limitations=tuple(dict.fromkeys(limitations)),
        ready_for_reasoning=ready,
        evidence_package=tuple(package),
    )
