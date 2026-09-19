"""Build a compact, auditable trail for autonomous engineering investigations."""
from __future__ import annotations
from typing import Any

def build_investigation_trail(*, goal: str, synthesis: dict[str, Any], hypotheses: list[dict[str, Any]]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for h in hypotheses:
        if not isinstance(h, dict): continue
        entries.append({
            "type":"hypothesis_assessment","hypothesis_id":h.get("id"),
            "statement":h.get("statement"),"status":h.get("evidence_status"),
            "supporting_count":len(h.get("supporting_independent_evidence") or []),
            "contradicting_count":len(h.get("contradicting_independent_evidence") or []),
            "missing_evidence":list(h.get("missing_evidence") or []),
            "causal_status":h.get("causal_status"),
        })
    autonomous=synthesis.get("autonomous_investigation") if isinstance(synthesis.get("autonomous_investigation"),dict) else {}
    for r in autonomous.get("rounds",[]) if isinstance(autonomous.get("rounds"),list) else []:
        if not isinstance(r,dict): continue
        plan=r.get("plan") if isinstance(r.get("plan"),dict) else {}
        entries.append({
            "type":"autonomous_round","round":r.get("round"),"focus":plan.get("focus"),
            "actions":[{"tool":a.get("tool"),"reason":a.get("reason")} for a in plan.get("actions",[]) if isinstance(a,dict)],
            "new_evidence_count":r.get("new_evidence_count"),
        })
    return {
        "goal":goal,"entries":entries,
        "stop_reason":autonomous.get("stop_reason"),
        "rounds_completed":autonomous.get("rounds_completed",0),
        "evidence_count":synthesis.get("evidence_count",0),
        "causal_conclusion":"not_established",
        "process_control_actions_allowed":False,
    }
