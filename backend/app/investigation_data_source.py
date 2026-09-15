"""Operational data-source selection for autonomous investigations.

Development investigations use deterministic synthetic site data and are marked
SIMULATED at the source. Configured deployments use the normal read-only
TagService/PI path. The two modes share the same governed tool contract.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import os
from typing import Any

from .simulator import SimulatedSiteSource
from .site_model import load_site_model
from .tag_service import TagService


class SimulatedInvestigationTagService:
    data_quality = "simulated"
    source_label = "development-simulator"

    def __init__(self) -> None:
        self.site = load_site_model()
        self.source = SimulatedSiteSource(self.site)

    def search(self, query: str) -> list[dict[str, Any]]:
        needle = query.strip().casefold()
        tokens = {token for token in needle.replace("?", " ").replace(";", " ").split() if len(token) > 2}
        ranked: list[tuple[int, dict[str, Any]]] = []
        for unit in self.site.units:
            for tag in unit.tags:
                haystack = " ".join((tag.key, tag.label, tag.semantic, *tag.aliases)).casefold()
                score = sum(1 for token in tokens if token in haystack)
                if score:
                    ranked.append((score, {"key": tag.key, "name": tag.label, "unit": tag.unit, "unit_key": unit.key, "semantic_key": tag.semantic, "data_quality": self.data_quality, "source": self.source_label}))
        ranked.sort(key=lambda item: (-item[0], item[1]["key"]))
        return [item for _, item in ranked]

    async def recorded_values(self, key: str, start_time: str, end_time: str, max_count: int = 1000) -> dict[str, Any]:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        duration_minutes = max(1, int((end - start).total_seconds() / 60))
        step_minutes = max(1, duration_minutes // max(2, min(max_count, 500)))
        data = self.source.recorded_values(key, start, end, step_minutes)
        return {"tag": key, "data": data, "data_quality": self.data_quality, "source": self.source_label, "read_only": True}


def investigation_tag_service() -> tuple[Any, dict[str, Any]]:
    """Return the process source plus metadata that must be propagated to the UI."""
    force_simulated = os.environ.get("FCC_INVESTIGATION_DATA_MODE", "").strip().casefold() == "simulated"
    pi_configured = bool(os.environ.get("FCC_PI_WEB_API_URL", "").strip())
    if force_simulated or not pi_configured:
        service = SimulatedInvestigationTagService()
        return service, {"mode": "simulated", "data_quality": "SIMULATED", "source": service.source_label, "process_writes": False}
    service = TagService()
    return service, {"mode": "historian", "data_quality": "HISTORIAN", "source": "configured-read-only-pi", "process_writes": False}
