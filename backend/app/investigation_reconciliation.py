"""Reconcile autonomous follow-up tool results into structured investigation state."""
from __future__ import annotations
from typing import Any

def _successful_data(run:dict[str,Any],tool:str)->list[Any]:
    executions=run.get("executions") if isinstance(run.get("executions"),list) else []
    rows=[]
    for execution in executions:
        if not isinstance(execution,dict):continue
        step=execution.get("step") if isinstance(execution.get("step"),dict) else {}
        result=execution.get("result") if isinstance(execution.get("result"),dict) else {}
        if step.get("tool_name")!=tool or execution.get("status")!="succeeded":continue
        data=result.get("data")
        if isinstance(data,list):rows.extend(data)
        elif data is not None:rows.append(data)
    return rows

def reconcile_follow_up(synthesis:dict[str,Any],result:dict[str,Any])->dict[str,Any]:
    run=result.get("run") if isinstance(result.get("run"),dict) else {}
    archive=_successful_data(run,"search_archive")
    events=_successful_data(run,"search_alarms_events")
    episodes=_successful_data(run,"find_similar_episodes")
    if archive:
        current=synthesis.get("archive_evidence") if isinstance(synthesis.get("archive_evidence"),dict) else {}
        items=[*(current.get("items") or []),*archive]
        current.update({"attempted":True,"items":items,"count":len(items),"approved_only":True})
        synthesis["archive_evidence"]=current;synthesis["archive_evidence_useful"]=True
    if events:
        current=synthesis.get("event_evidence") if isinstance(synthesis.get("event_evidence"),dict) else {}
        current.update({"attempted":True,"items":[*(current.get("items") or []),*events],"count":int(current.get("count") or 0)+len(events),"run":run})
        synthesis["event_evidence"]=current
    if episodes:
        current=synthesis.get("similar_episodes") if isinstance(synthesis.get("similar_episodes"),dict) else {}
        current.update({"attempted":True,"items":[*(current.get("items") or []),*episodes],"count":int(current.get("count") or 0)+len(episodes),"run":run})
        synthesis["similar_episodes"]=current
    return {"archive_added":len(archive),"events_added":len(events),"episodes_added":len(episodes)}
