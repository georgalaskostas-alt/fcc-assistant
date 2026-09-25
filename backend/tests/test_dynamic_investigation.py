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



def test_followup_context_prefers_matching_previous_dp_tag():
    tags = ["regenerator_dp", "regenerator_o2", "regenerator_temp"]

    matches = DynamicInvestigator._match_inherited_tags(
        "Ποιο ήταν το μέγιστο ΔP και τι ώρα συνέβη;",
        tags,
    )

    assert matches == ["regenerator_dp"]


def test_followup_context_prefers_matching_previous_o2_tag():
    tags = ["regenerator_dp", "regenerator_o2", "regenerator_temp"]

    matches = DynamicInvestigator._match_inherited_tags(
        "Και το O2;",
        tags,
    )

    assert matches == ["regenerator_o2"]


def test_followup_context_does_not_encode_fcc_specific_equipment():
    tags = ["compressor_pressure", "compressor_temperature", "compressor_speed"]

    matches = DynamicInvestigator._match_inherited_tags(
        "What was the maximum pressure?",
        tags,
    )

    assert matches == ["compressor_pressure"]

def test_followup_context_prefers_dp_when_equipment_name_is_also_present():
    tags = ["regenerator_dp", "regenerator_o2", "regenerator_temp"]
    matches = DynamicInvestigator._match_inherited_tags(
        "Ποιο ήταν το μέγιστο ΔP του regenerator και τι ώρα συνέβη;",
        tags,
    )
    assert matches == ["regenerator_dp"]


def test_followup_context_keeps_equipment_scope_when_no_variable_is_named():
    tags = ["regenerator_dp", "regenerator_o2", "regenerator_temp"]
    matches = DynamicInvestigator._match_inherited_tags(
        "Τι έγινε στο regenerator;",
        tags,
    )
    assert matches == tags
