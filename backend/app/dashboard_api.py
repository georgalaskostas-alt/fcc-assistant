from __future__ import annotations

import asyncio
import re
import time
import traceback
from fastapi import APIRouter
from pydantic import BaseModel, Field
from .dashboard_agent import plan_with_local_agent
from .dashboard_config import DashboardCommandError, plan_dashboard_command
from .dashboard_constraints import conflicts_with_current_turn, explicit_action
from .dashboard_dialogue import DashboardDialogueStore, contextual_plan, resolve_units
from .dashboard_pending import DashboardPendingStore
from .dashboard_store import DashboardStore
from .diagnostic_trace import append_trace, clear_trace, recent_trace
from .language import detect_user_language
from .site_model import load_site_model, site_runtime_status

router=APIRouter(prefix="/api/v1/dashboard",tags=["dashboard"])
class DashboardCommandRequest(BaseModel): command:str=Field(min_length=1,max_length=4000); workspace:str=Field(default="default",min_length=1,max_length=120); command_id:str|None=Field(default=None,max_length=120)
class DashboardSaveRequest(BaseModel): title:str=Field(default="Operations Overview",min_length=1,max_length=200); widgets:list[dict[str,object]]=Field(default_factory=list)

_command_gate:asyncio.Lock|None=None
_command_cache:dict[str,tuple[float,dict[str,object]]]={}
_COMMAND_CACHE_TTL=8.0

def _gate()->asyncio.Lock:
    global _command_gate
    if _command_gate is None:_command_gate=asyncio.Lock()
    return _command_gate

def _command_key(request:DashboardCommandRequest)->str:
    if request.command_id:return f"id:{request.command_id}"
    normalized=" ".join(request.command.casefold().split())
    return f"text:{request.workspace}:{normalized}"

@router.get("/site")
def dashboard_site()->dict[str,object]:
    site=load_site_model();return {"name":site.name,"units":site.list_units(),"read_only":True}
@router.get("/site/status")
def dashboard_site_status()->dict[str,object]:return site_runtime_status()
@router.get("/diagnostics")
def dashboard_diagnostics(limit:int=30)->dict[str,object]:return {"local_only":True,"events":recent_trace(limit)}
@router.delete("/diagnostics")
def dashboard_diagnostics_clear()->dict[str,object]:clear_trace();return {"cleared":True,"local_only":True}
@router.get("/workspaces/{workspace}")
def dashboard_workspace(workspace:str)->dict[str,object]:return DashboardStore().get(workspace)
@router.put("/workspaces/{workspace}")
def dashboard_workspace_save(workspace:str,request:DashboardSaveRequest)->dict[str,object]:return DashboardStore().put(workspace,request.model_dump())

def _steps(plan):
    if str(plan.get("action",""))!="transaction":return [plan]
    raw=plan.get("steps");return [x for x in raw if isinstance(x,dict)] if isinstance(raw,list) else []
def _planned_unit_keys(plan):
    keys=set()
    for step in _steps(plan):
        if str(step.get("action","")) in {"answer","clarify","remove_widget","remove_widgets","update_widgets","resize_widget","move_between"}:continue
        candidates=[]
        if isinstance(step.get("widget"),dict):candidates.append(step["widget"])
        if isinstance(step.get("widgets"),list):candidates.extend(x for x in step["widgets"] if isinstance(x,dict))
        keys.update(str(x.get("unit_key","")).casefold() for x in candidates if x.get("unit_key"))
    return keys
def _validate_unit_intent(command,site,aliases,plan):
    requested={u.key.casefold() for u in resolve_units(command,site,aliases)};planned=_planned_unit_keys(plan)
    if requested and planned and not planned.issubset(requested):raise DashboardCommandError("Κατάλαβα διαφορετική μονάδα από αυτή που ζήτησες. Δεν άλλαξα τίποτα.")
def _validate_transaction(plan):
    steps=_steps(plan);allowed={"add_widget","add_widgets","remove_widget","remove_widgets","replace_widget","update_widgets","resize_widget","move_between","answer"}
    if not steps or any(str(s.get("action","")) not in allowed for s in steps):raise DashboardCommandError("Δεν μπόρεσα να επαληθεύσω με ασφάλεια όλη τη σύνθετη εντολή. Δεν άλλαξα τίποτα.")
    return steps

_explicit_action=explicit_action

def _metric_filter(text):
    compact=re.sub(r"[^a-z0-9α-ωάέήίόύώ]+","",text.casefold())
    if any(token in compact for token in ("feedflow","παροχηfeed","τροφοδοσια")) or "feed" in text.casefold():return "feed"
    if any(token in compact for token in ("reactortemp","reactortemperature","θερμοκρασιαreactor","θερμοκρασιααντιδραστηρα")):return "reactor"
    if "regenerator" in text.casefold() or "αναγεννη" in text.casefold():return "regenerator"
    return None

def _widget_matches_metric(widget,metric_filter):
    hay=" ".join([str(widget.get("id","")),str(widget.get("title","")),*(str(v) for v in (widget.get("tag_keys") or []))]).casefold()
    if metric_filter=="feed":return "feed" in hay
    if metric_filter=="reactor":return "reactor" in hay and "temp" in hay
    if metric_filter=="regenerator":return "regenerator" in hay
    return True

def _period_followup_plan(command,state,action_context,widgets,explicit_units):
    text=command.casefold().strip()
    if _explicit_action(text) in {"add","remove","restore","replace"}:return None
    match=re.search(r"(?<!\d)(\d{1,3})\s*(?:h|hr|hrs|hour|hours|ωρ(?:α|ες|ών)?|ωρες|ώρα|ώρες)(?!\w)",text,re.I)
    if not match:return None
    period=f"{int(match.group(1))}h"
    trends=[w for w in widgets if str(w.get("type","")).casefold()=="trend" and w.get("id")]
    if not trends:return None
    unit_keys={u.key.casefold() for u in explicit_units}
    if unit_keys:trends=[w for w in trends if str(w.get("unit_key","")).casefold() in unit_keys]
    graph_words=any(x in text for x in ("διάγραμ","διαγραμ","γράφημ","γραφημ","trend","chart"))
    plural_followup=any(x in text for x in ("τελικά τα","τελικα τα","τα θέλω","τα θελω","κάν' τα","καν' τα","κάντα","καντα","και τα δύο","και τα δυο","και στις δύο","και στις δυο","στις δύο","στις δυο","both"))
    singular_followup=any(x in text for x in ("κάν' το","καν' το","κάν το","καν το","κάντο","καντο","άλλαξέ το","αλλαξε το","άλλαξέτο","αλλαξετο","make it","change it","set it"))
    metric=_metric_filter(text)
    if metric:trends=[w for w in trends if _widget_matches_metric(w,metric)]
    touched_raw=action_context.get("last_touched_widget_ids") if isinstance(action_context,dict) else None
    touched={str(v) for v in touched_raw} if isinstance(touched_raw,list) else set()
    touched_trends=[w for w in trends if str(w.get("id")) in touched] if touched else []
    last_widget=state.get("last_widget") if isinstance(state,dict) else None
    last_widget_id=str(last_widget.get("id")) if isinstance(last_widget,dict) and last_widget.get("id") else ""
    if not metric and not unit_keys:
        if singular_followup:
            if len(touched_trends)==1:trends=touched_trends
            elif last_widget_id:
                last_hits=[w for w in trends if str(w.get("id"))==last_widget_id]
                if len(last_hits)==1:trends=last_hits
        elif plural_followup and touched_trends:
            trends=touched_trends
    prior_mutation=str(action_context.get("last_action","")).casefold() in {"transaction","add_widget","add_widgets","update_widgets","replace_widget"}
    prior_dialogue_mutation=str(state.get("last_action","")).casefold() in {"transaction","add_widget","add_widgets","update_widgets","replace_widget"}
    contextual_followup=plural_followup or singular_followup
    has_reference=bool(touched_trends) or bool(last_widget_id)
    if not unit_keys and not metric and not graph_words and not (contextual_followup and (prior_mutation or prior_dialogue_mutation or has_reference)):return None
    if singular_followup and not unit_keys and not metric and len(trends)!=1:return None
    if not trends:return None
    ids=[str(w["id"]) for w in trends]
    language=detect_user_language(command).response_language
    message=(f"Updated {len(ids)} widget{'s' if len(ids)!=1 else ''} to {period}." if language=="en" else f"Έγινε. Ενημέρωσα {len(ids)} γράφημα{'τα' if len(ids)!=1 else ''} σε {period}.")
    return {"action":"update_widgets","target_ids":ids,"period":period,"read_only":True,"requires_confirmation":False},message

def _legacy_plan(command,site,state,widgets,aliases):
    plan,message=contextual_plan(command,site,state,widgets,learned_aliases=aliases)
    if plan is not None:return plan,message
    resolved=resolve_units(command,site,aliases);working=f"{command} {' '.join(u.key for u in resolved)}" if resolved else command
    return plan_dashboard_command(working,site,current_widgets=widgets),None

def _widget_map(workspace):
    raw=workspace.get("widgets") if isinstance(workspace,dict) else None
    items=[x for x in raw if isinstance(x,dict)] if isinstance(raw,list) else []
    return {str(w.get("id")):w for w in items if w.get("id")}

def _verified_message(command,plan,before,after,original_message):
    language=detect_user_language(command).response_language
    before_map=_widget_map(before);after_map=_widget_map(after)
    added=[w for key,w in after_map.items() if key not in before_map]
    removed=[w for key,w in before_map.items() if key not in after_map]
    changed=[w for key,w in after_map.items() if key in before_map and w!=before_map[key]]
    action=str(plan.get("action",""))
    if action in {"answer","clarify"}:return original_message
    if added and not removed:
        units=sorted({str(w.get("unit_key","")).upper() for w in added if w.get("unit_key")})
        label=", ".join(units)
        return (f"Added {len(added)} widget{'s' if len(added)!=1 else ''}{' in '+label if label else ''}." if language=="en" else f"Έγινε. Πρόσθεσα {len(added)} γράφημα{'τα' if len(added)!=1 else ''}{' σε '+label if label else ''}.")
    if removed and not added:
        return (f"Removed {len(removed)} widget{'s' if len(removed)!=1 else ''}." if language=="en" else f"Έγινε. Αφαίρεσα {len(removed)} γράφημα{'τα' if len(removed)!=1 else ''}.")
    if changed and not added and not removed:
        periods=sorted({str(w.get("period")) for w in changed if w.get("period")})
        suffix=f" to {periods[0]}" if language=="en" and len(periods)==1 else f" σε {periods[0]}" if language!="en" and len(periods)==1 else ""
        return (f"Updated {len(changed)} widget{'s' if len(changed)!=1 else ''}{suffix}." if language=="en" else f"Έγινε. Ενημέρωσα {len(changed)} γράφημα{'τα' if len(changed)!=1 else ''}{suffix}.")
    if added or removed or changed:
        return (f"Done. Verified workspace changes: +{len(added)} / -{len(removed)} / updated {len(changed)}." if language=="en" else f"Έγινε. Επιβεβαίωσα τις αλλαγές: +{len(added)} / -{len(removed)} / ενημερώθηκαν {len(changed)}.")
    return ("The command produced no workspace change." if language=="en" else "Η εντολή δεν προκάλεσε αλλαγή στο workspace.")

def _safe_failure(request,current,widgets,dialogue,pending_store,route,exc):
    append_trace("command.error",{"command":request.command,"command_id":request.command_id,"route":route,"error_type":type(exc).__name__,"error":str(exc),"traceback":"".join(traceback.format_exception(type(exc),exc,exc.__traceback__))[-6000:]})
    english=detect_user_language(request.command).response_language=="en"
    message="The action failed locally. I changed nothing." if english else "Δεν ολοκληρώθηκε η ενέργεια λόγω τοπικού σφάλματος. Δεν άλλαξα τίποτα."
    plan={"action":"clarify","read_only":True,"requires_confirmation":False,"needs_clarification":True}
    try:dialogue.remember(request.workspace,request.command,plan,current,message,previous_widgets=widgets)
    except Exception as remember_exc:append_trace("command.error.remember",{"command_id":request.command_id,"error_type":type(remember_exc).__name__,"error":str(remember_exc)})
    try:pending=pending_store.get(request.workspace)
    except Exception:pending=None
    try:site_status=site_runtime_status()
    except Exception:site_status={"status":"unavailable","read_only":True}
    return {"plan":plan,"workspace":current,"message":message,"needs_clarification":True,"agent":route,"pending_intent":pending,"site":site_status,"error":{"type":type(exc).__name__,"message":str(exc)}}

@router.post("/command")
async def dashboard_command(request:DashboardCommandRequest)->dict[str,object]:
    key=_command_key(request)
    async with _gate():
        now=time.monotonic()
        stale=[k for k,(created,_) in _command_cache.items() if now-created>_COMMAND_CACHE_TTL]
        for k in stale:_command_cache.pop(k,None)
        cached=_command_cache.get(key)
        if cached is not None:
            append_trace("command.deduplicated",{"command":request.command,"workspace":request.workspace,"command_id":request.command_id,"age_ms":round((now-cached[0])*1000)})
            return cached[1]
        try:result=await _execute_dashboard_command(request)
        except Exception as exc:
            try:
                current=DashboardStore().get(request.workspace);raw=current.get("widgets");widgets=[dict(x) for x in raw if isinstance(x,dict)] if isinstance(raw,list) else []
            except Exception:
                current={"workspace":request.workspace,"title":"Operations Overview","widgets":[]};widgets=[]
            result=_safe_failure(request,current,widgets,DashboardDialogueStore(),DashboardPendingStore(),"unhandled",exc)
        _command_cache[key]=(time.monotonic(),result)
        return result

async def _execute_dashboard_command(request:DashboardCommandRequest)->dict[str,object]:
    store=DashboardStore();dialogue=DashboardDialogueStore();pending_store=DashboardPendingStore();current=store.get(request.workspace);raw=current.get("widgets");widgets=[dict(x) for x in raw if isinstance(x,dict)] if isinstance(raw,list) else [];route="unknown"
    try:
        site=load_site_model();aliases=dialogue.aliases();explicit=resolve_units(request.command,site,aliases);pending=pending_store.get(request.workspace)
        append_trace("command.received",{"command":request.command,"workspace":request.workspace,"command_id":request.command_id,"language":detect_user_language(request.command).detected,"explicit_units":[u.key for u in explicit],"pending_intent":pending,"widgets_before":[{"id":w.get("id"),"unit_key":w.get("unit_key"),"tag_keys":w.get("tag_keys"),"type":w.get("type"),"period":w.get("period")} for w in widgets]})
        if len(explicit)==1:dialogue.remember_requested_unit(request.workspace,explicit[0].key)
        state=dialogue.get_state(request.workspace)
        if pending is not None:state["pending_intent"]=pending
        action_context=dialogue.get_action_context(request.workspace)
        deterministic_update=_period_followup_plan(request.command,state,action_context,widgets,explicit)
        command_action=_explicit_action(request.command)
        if deterministic_update is not None:
            plan,message=deterministic_update;route="verified-context-update";append_trace("command.context_resolved",{"command":request.command,"plan":plan,"reason":"explicit-period-followup","action_context":action_context})
        elif command_action is not None:
            # Explicit imperative dashboard commands are deterministic and should never
            # wait on the local LLM. This keeps common operator interactions sub-second
            # and leaves the LLM for genuinely conversational/ambiguous requests.
            plan,message=_legacy_plan(request.command,site,state,widgets,aliases);route="deterministic-explicit-fastpath"
            append_trace("command.fastpath",{"command":request.command,"explicit_action":command_action,"explicit_units":[u.key for u in explicit],"plan":plan})
        else:
            agent_result=await plan_with_local_agent(request.command,site,state,widgets)
            if agent_result is not None:plan,message=agent_result.plan,agent_result.message;route="local-llm"
            else:plan,message=_legacy_plan(request.command,site,state,widgets,aliases);route="deterministic-fallback"

        explicit_unit_keys={u.key.casefold() for u in explicit}
        conflicts=conflicts_with_current_turn(request.command,plan,explicit_unit_keys,widgets)
        if conflicts and route=="local-llm":
            append_trace("command.constraint_rejected",{"command":request.command,"route":route,"plan":plan,"conflicts":conflicts,"explicit_units":sorted(explicit_unit_keys),"recovery":"deterministic-replan"})
            fallback_plan,fallback_message=_legacy_plan(request.command,site,state,widgets,aliases)
            fallback_conflicts=conflicts_with_current_turn(request.command,fallback_plan,explicit_unit_keys,widgets)
            if not fallback_conflicts:
                plan,message=fallback_plan,fallback_message;route="constraint-recovered-fallback"
                append_trace("command.constraint_recovered",{"command":request.command,"plan":plan,"explicit_units":sorted(explicit_unit_keys)})
            else:
                conflicts=fallback_conflicts
        if conflicts_with_current_turn(request.command,plan,explicit_unit_keys,widgets):
            append_trace("command.constraint_blocked",{"command":request.command,"route":route,"plan":plan,"conflicts":conflicts_with_current_turn(request.command,plan,explicit_unit_keys,widgets)})
            english=detect_user_language(request.command).response_language=="en"
            raise DashboardCommandError("The proposed action conflicts with your current instruction. I changed nothing." if english else "Η προτεινόμενη ενέργεια δεν συμφωνεί με αυτό που ζήτησες τώρα. Δεν άλλαξα τίποτα.")

        _validate_unit_intent(request.command,site,aliases,plan);steps=_validate_transaction(plan) if str(plan.get("action",""))=="transaction" else []
    except DashboardCommandError as exc:
        message=str(exc);plan={"action":"clarify","read_only":True,"requires_confirmation":False,"needs_clarification":True};dialogue.remember(request.workspace,request.command,plan,current,message,previous_widgets=widgets);append_trace("command.rejected",{"command":request.command,"route":route,"message":message,"pending_intent":pending_store.get(request.workspace)});return {"plan":plan,"workspace":current,"message":message,"needs_clarification":True,"agent":route,"language":detect_user_language(request.command).response_language,"site":site_runtime_status()}
    except Exception as exc:return _safe_failure(request,current,widgets,dialogue,pending_store,route,exc)
    action=str(plan.get("action",""))
    try:
        if action=="clarify":
            frame=plan.get("pending_intent")
            if isinstance(frame,dict):pending_store.set(request.workspace,frame);append_trace("command.pending",{"workspace":request.workspace,"pending_intent":frame})
            workspace=current
        else:
            workspace=store.apply_transaction(request.workspace,steps) if action=="transaction" else store.apply_plan(request.workspace,plan)
            if action!="answer":pending_store.clear(request.workspace)
    except Exception as exc:return _safe_failure(request,current,widgets,dialogue,pending_store,route,exc)
    message=_verified_message(request.command,plan,current,workspace,message)
    append_trace("command.executed",{"command":request.command,"route":route,"plan":plan,"message":message,"pending_after":pending_store.get(request.workspace),"widgets_after":[{"id":w.get("id"),"unit_key":w.get("unit_key"),"tag_keys":w.get("tag_keys"),"type":w.get("type"),"period":w.get("period")} for w in (workspace.get("widgets") or []) if isinstance(w,dict)]})
    dialogue.remember(request.workspace,request.command,plan,workspace,message,previous_widgets=widgets)
    return {"plan":plan,"workspace":workspace,"message":message,"needs_clarification":bool(plan.get("needs_clarification",False)),"agent":route,"language":detect_user_language(request.command).response_language,"pending_intent":pending_store.get(request.workspace),"site":site_runtime_status()}
