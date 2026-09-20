"""Continue a saved investigation from its durable checkpoint."""
from __future__ import annotations
from typing import Any
from .agent_tools import ToolContext, ToolRegistry
from .investigation_loop import run_autonomous_evidence_loop
from .investigation_store import InvestigationStore
from .investigation_reasoning import reason_about_investigation
from .investigation_access import authorize_investigation

async def continue_saved_investigation(*, registry:ToolRegistry,store:InvestigationStore,
                                       investigation_id:str,context:ToolContext,
                                       data_source:dict[str,Any],max_rounds:int=3)->dict[str,Any]:
    item=store.get(investigation_id)
    if item is None: raise ValueError("Unknown investigation")
    authorize_investigation(item,context)
    resume=dict(item.resume_context)
    unit_key=str(resume.get("unit_key") or item.unit_key or context.scope_id)
    if not context.access.permits_scope(context.refinery,scope_kind=context.scope_kind,scope_id=unit_key):
        raise PermissionError("Investigation is not available in the active authorization context")
    item=store.resume(item.id)
    synthesis={
        "unit_key":unit_key,
        "time_window":dict(resume.get("time_window") or {}),
        "resolved_tags":list(resume.get("resolved_tags") or []),
        "last_autonomous_focus":resume.get("last_autonomous_focus"),
        "autonomous_rounds_completed":int(resume.get("autonomous_rounds_completed") or 0),
        "evidence_package":[{"evidence_id":e.source_id,"description":e.summary,"data":e.payload,"provenance":e.provenance} for e in item.evidence],
        "evidence_count":len(item.evidence),
        "archive_evidence":{},
        "event_evidence":{},
        "similar_episodes":{},
        "ready_for_reasoning":bool(item.evidence),
        "limitations":[],
    }
    window=synthesis["time_window"]
    loop=await run_autonomous_evidence_loop(registry=registry,context=context,goal=item.goal,unit_key=unit_key,
        synthesis=synthesis,time_window={"start":window.get("start",""),"end":window.get("end","")},
        episode_context={},max_rounds=max_rounds)
    synthesis["autonomous_investigation"]=loop
    reasoning=await reason_about_investigation(goal=item.goal,synthesis=synthesis,data_source=data_source)
    trail=reasoning.get("investigation_trail") if isinstance(reasoning.get("investigation_trail"),dict) else {}
    item=store.save_checkpoint(item.id,trail=trail,resume_context={
        **resume,"unit_key":unit_key,"time_window":window,"resolved_tags":synthesis["resolved_tags"],
        "last_autonomous_focus":synthesis.get("last_autonomous_focus"),
        "autonomous_rounds_completed":int(resume.get("autonomous_rounds_completed") or 0)+int(loop.get("rounds_completed") or 0),
        "evidence_count":synthesis.get("evidence_count",0),
    })
    return {"investigation":item.to_dict(),"continuation":loop,"reasoning":reasoning,"read_only":True}
