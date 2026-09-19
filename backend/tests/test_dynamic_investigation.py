import pytest
from backend.app.dynamic_investigation import DynamicInvestigator


def test_expansion_queries_are_generic_and_bounded():
    queries = DynamicInvestigator._expansion_queries(
        "Why did pressure increase?", ["unit_dp", "unit_temp", "unit_o2"]
    )
    assert queries[0] == "Why did pressure increase?"
    assert len(queries) <= 8
    assert any("unit_dp" in q for q in queries)
    # The adaptive planner must not encode FCC-specific causal tag lists.
    joined = " ".join(queries).casefold()
    assert "catalyst circulation" not in joined
    assert "regenerator air" not in joined


def test_tag_key_extraction_deduplicates_and_bounds():
    rows = [{"key": f"tag_{i}"} for i in range(20)] + [{"key": "tag_0"}]
    keys = DynamicInvestigator._tag_keys(rows, limit=4)
    assert keys == ["tag_0", "tag_1", "tag_2", "tag_3"]
