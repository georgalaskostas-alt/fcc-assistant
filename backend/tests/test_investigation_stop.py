from backend.app.investigation_stop import classify_execution_boundary,normalize_stop_reason

def test_normalizes_stop_reasons():
    assert normalize_stop_reason("evidence_saturated")=="evidence_sufficient_for_bounded_assessment"
    assert normalize_stop_reason("max_rounds_reached")=="iteration_budget_exhausted"
    assert normalize_stop_reason("tool_budget_exhausted")=="tool_budget_exhausted"

def test_permission_failure_is_explicit():
    result={"run":{"executions":[{"status":"failed","error":"Tool not permitted for this scope"}]}}
    assert classify_execution_boundary(result)=="permission_boundary"

def test_source_failure_is_explicit():
    result={"run":{"executions":[{"status":"failed","error":"historian source unavailable"}]}}
    assert classify_execution_boundary(result)=="source_unavailable"
