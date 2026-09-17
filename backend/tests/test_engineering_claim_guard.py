from backend.app.engineering_claim_guard import validate_engineering_narrative
from backend.app.process_analytics import pearson


def test_rejects_speculative_mechanism_language_seen_in_local_model_output():
    result = validate_engineering_narrative("The correlation suggests a possible mechanism where temperature changes could influence DP.")
    assert result["valid"] is False
    assert any(item["type"] == "unsupported_mechanism" for item in result["violations"])


def test_rejects_unproved_baseline_statement():
    result = validate_engineering_narrative("The observed changes are within the simulated data's variability.")
    assert result["valid"] is False
    assert any(item["type"] == "unsupported_baseline" for item in result["violations"])


def test_rejects_units_not_grounded_by_tag_metadata():
    result = validate_engineering_narrative("DP increased from 0.72 bar to 0.84 bar.")
    assert result["valid"] is False
    assert any(item["type"] == "ungrounded_engineering_unit" for item in result["violations"])


def test_allows_unit_when_source_metadata_explicitly_supplies_it():
    result = validate_engineering_narrative("DP increased from 0.72 bar to 0.84 bar.", allowed_units={"bar"})
    assert result == {"valid": True, "violations": []}


def test_pearson_exposes_canonical_r_for_structured_claims():
    result = pearson([1, 2, 3, 4], [2, 4, 6, 8])
    assert result["available"] is True
    assert result["r"] == result["pearson_r"]
    assert result["r"] > 0.99
