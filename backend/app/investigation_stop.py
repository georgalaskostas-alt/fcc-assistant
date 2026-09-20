"""Canonical stop semantics for autonomous engineering investigations."""
from __future__ import annotations
from typing import Any

STOP_REASONS={
 "evidence_sufficient_for_bounded_assessment",
 "no_new_evidence",
 "iteration_budget_exhausted",
 "tool_budget_exhausted",
 "permission_boundary",
 "source_unavailable",
 "repeated_plan_no_new_direction",
}

def classify_execution_boundary(result:dict[str,Any])->str|None:
    run=result.get("run") if isinstance(result.get("run"),dict) else {}
    executions=run.get("executions") if isinstance(run.get("executions"),list) else []
    failures=[str(x.get("error") or "").casefold() for x in executions if isinstance(x,dict) and x.get("status")=="failed"]
    if not failures:return None
    permission_terms=("permission","not permitted","unauthorized","forbidden","scope","access denied")
    source_terms=("unavailable","not available","connection","timeout","source","offline")
    if any(any(t in err for t in permission_terms) for err in failures):return "permission_boundary"
    if any(any(t in err for t in source_terms) for err in failures):return "source_unavailable"
    return "source_unavailable"

def normalize_stop_reason(reason:str)->str:
    mapping={"evidence_saturated":"evidence_sufficient_for_bounded_assessment","max_rounds_reached":"iteration_budget_exhausted"}
    normalized=mapping.get(reason,reason)
    return normalized if normalized in STOP_REASONS else "source_unavailable"
