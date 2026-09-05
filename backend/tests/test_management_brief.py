from pathlib import Path

from app.engineering_context import EngineeringContextBuilder
from app.learned_patterns import LearnedPatternStore
from app.management_brief import ManagementBriefBuilder
from app.operational_episode import OperationalEpisodeStore
from app.production_domain import ProductionStore
from app.unit_knowledge import UnitKnowledgeStore


def test_management_brief_keeps_unit_contexts_separate(tmp_path: Path):
    knowledge = UnitKnowledgeStore(tmp_path / "knowledge.json")
    episodes = OperationalEpisodeStore(tmp_path / "episodes.json")
    patterns = LearnedPatternStore(tmp_path / "patterns.json")
    production = ProductionStore(tmp_path / "production.json")
    engineering = EngineeringContextBuilder(
        knowledge_store=knowledge,
        episode_store=episodes,
        pattern_store=patterns,
        production_store=production,
    )

    production.add(
        scope_kind="complex",
        scope_id="conversion",
        period_start="2026-08-23T00:00:00Z",
        period_end="2026-08-24T00:00:00Z",
        metric="throughput",
        actual=95,
        plan=100,
        unit="%",
    )

    brief = ManagementBriefBuilder(
        engineering_builder=engineering,
        production_store=production,
    ).build(
        scope_kind="complex",
        scope_id="conversion",
        unit_keys=["fcc", "hcu"],
        process_evidence_by_unit={
            "fcc": {"feed_rate": 270},
            "hcu": {"feed_rate": 180},
        },
    )

    assert set(brief["units"]) == {"fcc", "hcu"}
    assert brief["units"]["fcc"]["process_evidence"]["feed_rate"] == 270
    assert brief["units"]["hcu"]["process_evidence"]["feed_rate"] == 180
    assert brief["production_vs_plan"]["negative_variances"][0]["metric"] == "throughput"
    assert brief["briefing_policy"]["keep_unit_evidence_separate"] is True
