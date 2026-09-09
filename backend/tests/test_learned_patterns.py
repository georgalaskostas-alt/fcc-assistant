from pathlib import Path

from app.learned_patterns import LearnedPatternStore


def test_candidate_pattern_requires_repeated_evidence(tmp_path: Path):
    store = LearnedPatternStore(tmp_path / "patterns.json")
    try:
        store.add_candidate(
            unit_key="fcc",
            statement="candidate",
            context={"feed_family": "A"},
            outcome={"fuel_gas": "higher"},
            comparable_episodes=1,
            confidence=0.8,
        )
    except ValueError as exc:
        assert "at least two" in str(exc)
    else:
        raise AssertionError("single-episode pattern should be rejected")


def test_engineer_review_promotes_pattern_to_approved_knowledge(tmp_path: Path):
    store = LearnedPatternStore(tmp_path / "patterns.json")
    pattern = store.add_candidate(
        unit_key="fcc",
        statement="At comparable feed and rate, higher severity repeatedly coincided with higher gas make.",
        context={"feed_family": "A", "throughput_band": "high"},
        outcome={"fuel_gas": "higher"},
        comparable_episodes=31,
        confidence=0.82,
    )

    assert pattern.status == "candidate"
    approved = store.review(
        pattern.id,
        status="approved",
        reviewed_by="process-engineer",
        engineer_note="Consistent with unit behavior; retain feed-family qualification.",
    )

    assert approved.status == "approved"
    assert approved.evidence_level == "approved_unit_knowledge"
    assert approved.reviewed_by == "process-engineer"
