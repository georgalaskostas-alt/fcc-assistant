"""Planner for source-grounded refinery engineering investigations.

The planner turns an engineering goal into a governed AgentPlan. It does not
execute tools and cannot bypass ToolRegistry authorization. A local LLM planner
can replace/augment the deterministic heuristics later while keeping the same
plan contract and safety boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from .agent_runtime import AgentPlan, AgentStep


@dataclass(frozen=True)
class InvestigationIntent:
    goal: str
    unit_key: str
    subject: str
    start_time: str
    end_time: str
    archive_query: str


class InvestigationPlanner:
    def __init__(self, *, now_provider=None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def understand(self, goal: str, *, unit_key: str) -> InvestigationIntent:
        text = goal.strip()
        if not text:
            raise ValueError("Investigation goal is required")
        unit = unit_key.strip().casefold()
        if not unit:
            raise ValueError("unit_key is required")

        now = self._now_provider()
        lowered = text.casefold()
        if "χθες" in lowered or "yesterday" in lowered:
            day = (now - timedelta(days=1)).date()
            start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
            end = start + timedelta(days=1)
        elif "τελευταίες 24" in lowered or "last 24" in lowered:
            end = now
            start = now - timedelta(hours=24)
        else:
            end = now
            start = now - timedelta(hours=8)

        subject = self._subject(text)
        return InvestigationIntent(
            goal=text,
            unit_key=unit,
            subject=subject,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            archive_query=f"{subject} troubleshooting causes abnormal operation",
        )

    @staticmethod
    def _subject(goal: str) -> str:
        normalized = re.sub(r"[?!.,;:]", " ", goal).strip()
        # Keep engineering wording intact; tag resolution belongs to search_tags.
        for prefix in ("γιατί ", "why ", "τι προκάλεσε ", "what caused "):
            if normalized.casefold().startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        return normalized or goal.strip()

    def plan(self, goal: str, *, unit_key: str) -> AgentPlan:
        intent = self.understand(goal, unit_key=unit_key)
        steps = (
            AgentStep(
                id="resolve-tags",
                tool_name="search_tags",
                arguments={"query": intent.subject},
                description="Resolve relevant approved historian tags from the engineering question.",
            ),
            AgentStep(
                id="search-archive",
                tool_name="search_archive",
                arguments={
                    "query": intent.archive_query,
                    "unit_key": intent.unit_key,
                    "approved_only": True,
                    "limit": 8,
                },
                description="Search approved technical knowledge for causes, limits and troubleshooting guidance.",
            ),
        )
        return AgentPlan(goal=intent.goal, steps=steps)
