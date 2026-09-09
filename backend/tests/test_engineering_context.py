from pathlib import Path

from app.engineering_context import EngineeringContextBuilder
from app.learned_patterns import LearnedPatternStore
from app.operational_episode import OperationalEpisodeStore
from app.production_domain import ProductionStore
from app.unit_knowledge import UnitKnowledgeStore


def test_engineering_context_combines_approved_local_evidence(tmp_path: Path):
    knowledge = UnitKnowledgeStore(tmp_path / "knowledge.json")
    episodes = OperationalEpisodeStore(tmp_path / "episodes.json")
    patterns = LearnedPatternStore(tmp_path / "patterns.json")
    production = ProductionStore(tmp_path / "production.json")

    knowledge.add_override(
        "fcc",
        subject="FV-123 normal max",
        manual_value="65%",
        current_value="60%",
        reason="post-revamp hydraulic limitation",
        effective_from="2025-06-01T00:00:00Z",
        approved_by="process-engineer",
        status="approved",
    )
    episodes.add(
        unit_key="fcc",
        start_time="2026-08-20T07:00:00Z",
        end_time="2026-08-20T11:00:00Z",
        kind="stable",
        regime="high rate",
        outputs={"naphtha_rate": 82.0},
    )
    candidate = patterns.add_candidate(
        unit_key="fcc",
        statement="Higher severity repeatedly coincided with higher gas make under feed family A.",
        context={"feed_family": "A"},
        outcome={"fuel_gas": "higher"},
        comparable_episodes=10,
        confidence=0.8,
    )
    patterns.review(candidate.id, status="approved", reviewed_by="process-engineer")
    production.add(
        scope_kind="unit",
        scope_id="fcc",
        period_start="2026-08-23T00:00:00Z",
        period_end="2026-08-24T00:00:00Z",
        metric="throughput",
        actual=270.0,
        plan=280.0,
        unit="m3/h",
    )

    context = EngineeringContextBuilder(
        knowledge_store=knowledge,
        episode_store=episodes,
        pattern_store=patterns,
        production_store=production,
    ).for_unit("fcc", at_time="2026-08-23T12:00:00Z")

    assert context["knowledge"]["overrides"][0]["current_value"] == "60%"
    assert context["historical_episode_count"] == 1
    assert len(context["approved_learned_patterns"]) == 1
    assert context["production_vs_plan"]["negative_variances"][0]["metric"] == "throughput"
    assert context["reasoning_policy"]["plant_writes_allowed"] is False
