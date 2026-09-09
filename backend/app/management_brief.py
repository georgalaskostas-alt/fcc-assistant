from __future__ import annotations

from typing import Any

from .engineering_context import EngineeringContextBuilder
from .production_domain import ProductionStore


class ManagementBriefBuilder:
    """Aggregate bounded, unit-separated evidence for complex/refinery briefs."""

    def __init__(
        self,
        *,
        engineering_builder: EngineeringContextBuilder | None = None,
        production_store: ProductionStore | None = None,
    ) -> None:
        self.engineering_builder = engineering_builder or EngineeringContextBuilder()
        self.production_store = production_store or ProductionStore()

    def build(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        unit_keys: list[str],
        at_time: str | None = None,
        process_evidence_by_unit: dict[str, dict[str, object]] | None = None,
    ) -> dict[str, Any]:
        if scope_kind not in {"complex", "refinery"}:
            raise ValueError("management brief scope must be complex or refinery")
        normalized_units = list(dict.fromkeys(key.strip().casefold() for key in unit_keys if key.strip()))
        if not normalized_units:
            raise ValueError("at least one unit is required")

        process_evidence_by_unit = process_evidence_by_unit or {}
        units: dict[str, Any] = {}
        for unit_key in normalized_units:
            units[unit_key] = {
                "process_evidence": process_evidence_by_unit.get(unit_key, {}),
                "engineering_context": self.engineering_builder.for_unit(unit_key, at_time=at_time),
            }

        production = self.production_store.summary(scope_kind=scope_kind, scope_id=scope_id)
        return {
            "scope": {"kind": scope_kind, "id": scope_id.casefold()},
            "units": units,
            "production_vs_plan": production,
            "briefing_policy": {
                "rank_by_process_and_business_significance": True,
                "keep_unit_evidence_separate": True,
                "surface_missing_or_stale_data": True,
                "association_is_not_causation": True,
                "plant_writes_allowed": False,
                "external_process_ai_allowed": False,
            },
        }
