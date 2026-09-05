from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .learned_patterns import LearnedPatternStore
from .operational_episode import OperationalEpisodeStore, outcome_envelope
from .production_domain import ProductionStore
from .unit_knowledge import UnitKnowledgeStore


class EngineeringContextBuilder:
    """Assemble evidence-backed context for local process reasoning.

    The builder intentionally does not call an AI model. It only gathers local,
    version-aware evidence so higher layers can pass a bounded context to the
    embedded model.
    """

    def __init__(
        self,
        *,
        knowledge_store: UnitKnowledgeStore | None = None,
        episode_store: OperationalEpisodeStore | None = None,
        pattern_store: LearnedPatternStore | None = None,
        production_store: ProductionStore | None = None,
    ) -> None:
        self.knowledge_store = knowledge_store or UnitKnowledgeStore()
        self.episode_store = episode_store or OperationalEpisodeStore()
        self.pattern_store = pattern_store or LearnedPatternStore()
        self.production_store = production_store or ProductionStore()

    def for_unit(
        self,
        unit_key: str,
        *,
        at_time: str | None = None,
        configuration_version: str | None = None,
        comparison_context: dict[str, float | str] | None = None,
        similar_limit: int = 8,
    ) -> dict[str, Any]:
        knowledge = self.knowledge_store.effective_context(unit_key, at_time)
        episodes = self.episode_store.list(
            unit_key=unit_key,
            configuration_version=configuration_version,
        )
        approved_patterns = self.pattern_store.list(unit_key=unit_key, status="approved")
        candidates = self.pattern_store.list(unit_key=unit_key, status="candidate")
        production = self.production_store.summary(scope_kind="unit", scope_id=unit_key)

        similar: list[dict[str, Any]] = []
        if comparison_context:
            version = configuration_version or "current"
            similar = [
                {
                    "episode": asdict(item.episode),
                    "similarity": item.similarity,
                    "matched_features": list(item.matched_features),
                }
                for item in self.episode_store.similar(
                    unit_key=unit_key,
                    configuration_version=version,
                    context=comparison_context,
                    limit=similar_limit,
                )
            ]

        return {
            "unit_key": unit_key.casefold(),
            "knowledge": knowledge,
            "historical_episode_count": len(episodes),
            "historical_outcome_envelope": outcome_envelope(episodes),
            "approved_learned_patterns": [asdict(item) for item in approved_patterns],
            "candidate_patterns_for_review": [asdict(item) for item in candidates],
            "comparable_episodes": similar,
            "production_vs_plan": production,
            "reasoning_policy": {
                "priority": [
                    "actual_measured_data",
                    "approved_current_unit_knowledge",
                    "approved_revamp_context",
                    "manual_knowledge",
                    "approved_unit_specific_learned_patterns",
                    "repeated_associations",
                    "generic_chemical_engineering_knowledge",
                ],
                "association_is_not_causation": True,
                "plant_writes_allowed": False,
                "external_process_ai_allowed": False,
            },
        }
