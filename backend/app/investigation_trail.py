"""Build a compact, auditable trail for autonomous engineering investigations."""
from __future__ import annotations
from typing import Any

def _source_kind(item: dict[str, Any]) -> str:
    tool=str(item.get("tool") or item.get("type") or "")
    return {
        "get_history":"historian","search_alarms_events":"alarms_events",
        "search_archive":"technical_archive","find_similar_episodes":"previous_incident",
    }.get(tool, tool or "evidence")

def _evidence_graph(hypotheses: list[dict[str, Any]], synthesis: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]]=[]; edges: list[dict[str, Any]]=[]; seen:set[str]=set()
    for h in hypotheses:
        if not isinstance(h,dict): continue
        hid=str(h.get("id") or "")
        if not hid: continue
        nodes.append({"id":hid,"kind":"hypothesis","label":h.get("statement"),"status":h.get("evidence_status"),"causal_status":"not_established"});seen.add(hid)
        for relation,key in (("supports","supporting_independent_evidence"),("contradicts","contradicting_independent_evidence")):
            for i,e in enumerate(h.get(key) or []):
                if not isinstance(e,dict): continue
                eid=str(e.get("stable_evidence_id") or e.get("evidence_id") or e.get("id") or f"{hid}:{relation}:{i}")
                if eid not in seen:
                    nodes.append({"id":eid,"kind":"evidence","source_kind":_source_kind(e),"label":e.get("description") or e.get("title") or e.get("type") or eid,"provenance":dict(e.get("provenance") or {})});seen.add(eid)
                edges.append({"from":eid,"to":hid,"relation":relation})
        for i,e in enumerate(h.get("evidence_matches") or []):
            if not isinstance(e,dict): continue
            eid=str(e.get("stable_evidence_id") or e.get("evidence_id") or e.get("id") or f"{hid}:match:{i}")
            if eid not in seen:
                nodes.append({"id":eid,"kind":"evidence","source_kind":_source_kind(e),"label":e.get("description") or e.get("title") or e.get("type") or eid,"provenance":dict(e.get("provenance") or {})});seen.add(eid)
            relation=str(e.get("stance") or e.get("relation") or "related")
            edges.append({"from":eid,"to":hid,"relation":relation})
    return {"nodes":nodes,"edges":edges}

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
            "selected_hypothesis_id":plan.get("selected_hypothesis_id"),
            "selected_hypothesis_score":plan.get("selected_hypothesis_score"),
            "hypothesis_ranking":list(plan.get("hypothesis_ranking") or []),
            "hypothesis_branches":list(plan.get("hypothesis_branches") or []),
            "planning_mode":plan.get("planning_mode"),
            "semantic_candidates":list(plan.get("semantic_candidates") or []),
            "branch_lifecycle":list(r.get("hypothesis_branch_lifecycle") or []),
            "branch_lifecycle_after_evidence":list(r.get("branch_lifecycle_after_evidence") or []),
            "actions":[{
                "tool":a.get("tool"),"reason":a.get("reason"),"value":a.get("value"),
                "hypothesis_branch_id":a.get("hypothesis_branch_id"),"branch_score":a.get("branch_score"),
                "semantic_candidate":dict(a.get("semantic_candidate") or {}),
            } for a in plan.get("actions",[]) if isinstance(a,dict)],
            "realized_information_gain":list(r.get("realized_information_gain") or []),
            "returned_evidence_count":r.get("returned_evidence_count"),
            "new_evidence_count":r.get("new_evidence_count"),
            "new_evidence_ids":list(r.get("new_evidence_ids") or []),
            "reconciliation":dict(r.get("reconciliation") or {}),
        })
    return {
        "goal":goal,"entries":entries,
        "stop_reason":autonomous.get("stop_reason"),
        "rounds_completed":autonomous.get("rounds_completed",0),
        "budget":dict(autonomous.get("budget") or {}),
        "evidence_count":synthesis.get("evidence_count",0),
        "causal_conclusion":"not_established",
        "process_control_actions_allowed":False,
        "evidence_graph":_evidence_graph(hypotheses,synthesis),
    }
