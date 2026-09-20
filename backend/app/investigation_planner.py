"""Planner for source-grounded refinery engineering investigations.

Natural-language calendar periods are interpreted in the configured refinery
site timezone and converted to UTC for historian retrieval. The planner does
not execute tools and cannot bypass ToolRegistry authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .agent_runtime import AgentPlan, AgentStep


@dataclass(frozen=True)
class InvestigationIntent:
    goal: str
    unit_key: str
    subject: str
    start_time: str
    end_time: str
    archive_query: str
    period_interpretation: str = "rolling_8h"
    site_timezone: str = "UTC"


def _search_text(value: str) -> str:
    """Case/diacritic tolerant text used only for intent matching."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


class InvestigationPlanner:
    def __init__(self, *, now_provider=None, site_timezone: str | None = None) -> None:
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.site_timezone = site_timezone or os.getenv("FCC_SITE_TIMEZONE", "Europe/Athens")
        try:
            self._site_tz = ZoneInfo(self.site_timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown refinery site timezone: {self.site_timezone}") from exc

    def understand(self, goal: str, *, unit_key: str) -> InvestigationIntent:
        text = goal.strip()
        if not text:
            raise ValueError("Investigation goal is required")
        unit = unit_key.strip().casefold()
        if not unit:
            raise ValueError("unit_key is required")

        supplied_now = self._now_provider()
        if supplied_now.tzinfo is None:
            supplied_now = supplied_now.replace(tzinfo=timezone.utc)
        now_local = supplied_now.astimezone(self._site_tz)
        lowered = _search_text(text)

        # `_search_text` removes Greek diacritics, so match normalized Greek tokens.
        if "χθες" in lowered or "χτες" in lowered or "yesterday" in lowered:
            day = now_local.date() - timedelta(days=1)
            start_local = datetime.combine(day, datetime.min.time(), tzinfo=self._site_tz)
            end_local = start_local + timedelta(days=1)
            start, end, period = start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), "previous_local_calendar_day"
        elif "τελευταιες 24" in lowered or "τελευταια 24" in lowered or "last 24" in lowered:
            end = supplied_now.astimezone(timezone.utc)
            start = end - timedelta(hours=24)
            period = "rolling_24h"
        else:
            end = supplied_now.astimezone(timezone.utc)
            start = end - timedelta(hours=8)
            period = "rolling_8h"

        subject = self._subject(text)
        return InvestigationIntent(
            goal=text,
            unit_key=unit,
            subject=subject,
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            archive_query=f"{subject} troubleshooting causes abnormal operation",
            period_interpretation=period,
            site_timezone=self.site_timezone,
        )

    @staticmethod
    def _subject(goal: str) -> str:
        normalized = re.sub(r"[?!.,;:]", " ", goal).strip()
        searchable = _search_text(normalized)
        prefixes = (("γιατι ", "γιατί "), ("why ", "why "), ("τι προκαλεσε ", "τι προκάλεσε "), ("what caused ", "what caused "))
        for search_prefix, original_prefix in prefixes:
            if searchable.startswith(search_prefix):
                normalized = normalized[len(original_prefix):]
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
                arguments={"query": intent.archive_query, "unit_key": intent.unit_key, "approved_only": True, "limit": 8},
                description="Search approved technical knowledge for causes, limits and troubleshooting guidance.",
            ),
        )
        return AgentPlan(goal=intent.goal, steps=steps)
