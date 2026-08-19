from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .local_ai import LocalAIClient, LocalAIError
from .shift_report import ShiftReportEngine, ShiftReportError
from .tag_service import TagService, TagServiceError


class OrchestratorError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssistantAnswer:
    answer: str
    model: str
    evidence_type: str
    read_only: bool = True


class AssistantOrchestrator:
    """Coordinates approved FCC data tools and the local AI model."""

    def __init__(self, tag_service: TagService | None = None, local_ai: LocalAIClient | None = None) -> None:
        self.tag_service = tag_service or TagService()
        self.local_ai = local_ai or LocalAIClient()
        self.shift_reports = ShiftReportEngine(self.tag_service)

    async def analyze_shift(self, question: str, start_time: str, end_time: str, tag_keys: list[str] | None = None) -> AssistantAnswer:
        try:
            report = await self.shift_reports.generate(start_time=start_time, end_time=end_time, tag_keys=tag_keys)
            response = await self.local_ai.generate(user_prompt=question, context={
                "analysis_scope": "shift_report", "start_time": start_time,
                "end_time": end_time, "report": report,
            })
        except (ShiftReportError, TagServiceError, LocalAIError) as exc:
            raise OrchestratorError(str(exc)) from exc
        return AssistantAnswer(answer=response.text, model=response.model, evidence_type="shift_report")

    async def analyze_tag_period(self, question: str, tag_key: str, start_time: str, end_time: str) -> AssistantAnswer:
        try:
            evidence: dict[str, Any] = await self.tag_service.recorded_values(
                key=tag_key, start_time=start_time, end_time=end_time,
            )
            response = await self.local_ai.generate(user_prompt=question, context={
                "analysis_scope": "single_tag_period", "tag_key": tag_key,
                "start_time": start_time, "end_time": end_time, "evidence": evidence,
            })
        except (TagServiceError, LocalAIError) as exc:
            raise OrchestratorError(str(exc)) from exc
        return AssistantAnswer(answer=response.text, model=response.model, evidence_type="single_tag_period")
