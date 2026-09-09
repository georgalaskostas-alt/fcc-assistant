from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from .diagnostic_trace import append_trace
from .local_ai import LocalAIClient, LocalAIError
from .site_model import ProcessUnit, SiteModel, UnitTag


@dataclass(frozen=True)
class AgentResult:
    plan: dict[str, object]
    message: str


_AGENT_SYSTEM = """You are FCC Assistant, a refinery dashboard copilot. Behave like a competent human colleague, not a command parser. Understand conversational Greek, English, and mixed refinery language. Use CURRENT WIDGETS, RECENT TURNS, and PENDING INTENT to resolve ellipsis, pronouns, corrections, and follow-up answers.
Return ONLY JSON with {"operations":[{"action":"add|update|remove|remove_all|move|restore|answer|clarify","units":[],"metrics":[],"scope":"explicit|all_units|previous|null","reference":"last|all|removed_batch|widget id|description|null","widget_type":"trend|kpi|average|summary|null","period":"8h|null","missing":[]}],"answer":"short natural Greek response"}.
Rules:
- Merge newest utterance with pending/dialogue context; preserve known slots unless corrected.
- A request to change/make existing chart(s) to another time window is action=update, not add. Examples: "κάν' τα 8 ώρες", "τα διαγράμματα τελικά 8h", "change both charts to 8h" => update with period=8h.
- If plural charts/widgets are referenced without a narrower qualifier, reference=all. "στις δύο μονάδες", "και στις δύο", "σε κάθε μονάδα" => scope=all_units when appropriate.
- One metric across two units means two concrete widgets. Never invent units/metrics/ids/process facts.
- add requires resolvable units and metrics. update requires a period and resolvable existing widget target(s); it does NOT require a metric if context clearly identifies existing charts.
- "όλα τα γραφήματα από παντού" => remove_all scope=all_units. "βάλε τα πάλι πίσω" => restore reference=removed_batch.
- Clarify only when the target truly cannot be resolved from utterance + current widgets + context.
- Keep answer concise and natural for speech.
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw=text.strip(); raw=re.sub(r"^```(?:json)?\s*","",raw,flags=re.I); raw=re.sub(r"\s*```$","",raw)
    a,b=raw.find("{"),raw.rfind("}")
    if a<0 or b<a: raise ValueError("agent returned no JSON")
    obj=json.loads(raw[a:b+1])
    if not isinstance(obj,dict): raise ValueError("agent response must be object")
    return obj


def _catalog(site: SiteModel) -> list[dict[str, object]]:
    return [{"key":u.key,"name":u.name,"aliases":list(u.aliases),"metrics":[{"key":t.key,"label":t.label,"semantic":t.semantic,"aliases":list(t.aliases)} for t in u.tags]} for u in site.units]


def _find_unit(site: SiteModel,value: object)->ProcessUnit|None:
    return site.find_unit(value.strip()) if isinstance(value,str) and value.strip() else None


def _find_tag(unit:ProcessUnit,query:object)->UnitTag|None:
    if not isinstance(query,str) or not query.strip(): return None
    needle=query.strip().casefold(); exact=[]; partial=[]
    for tag in unit.tags:
        values=[x.casefold() for x in [tag.key,tag.label,tag.semantic,*tag.aliases] if x]
        if needle in values: exact.append(tag)
        elif any(needle in v or v in needle for v in values): partial.append(tag)
    return exact[0] if len(exact)==1 else partial[0] if not exact and len(partial)==1 else None


def _widget(unit:ProcessUnit,tag:UnitTag,kind:str,period:str,order:int)->dict[str,object]:
    kind=kind if kind in {"trend","kpi","average"} else "trend"; width,height=((12,"tall") if kind=="trend" else (4,"compact"))
    return {"id":f"{unit.key}-{tag.key}-{uuid.uuid4().hex[:8]}","type":kind,"title":tag.label,"unit_key":unit.key,"tag_keys":[tag.key],"period":period or "8h","layout":{"order":order,"width":width,"height":height}}


def _last(state:dict[str,object],widgets:list[dict[str,object]])->dict[str,object]|None:
    candidate=state.get("last_widget")
    if isinstance(candidate,dict):
        cid=str(candidate.get("id","")); hit=next((w for w in widgets if str(w.get("id",""))==cid),None)
        if hit:return hit
    return widgets[-1] if widgets else None


def _widget_matches_metric(widget:dict[str,object], metric:str, site:SiteModel)->bool:
    unit=site.find_unit(str(widget.get("unit_key","")))
    if not unit:return False
    tag=_find_tag(unit,metric)
    keys=widget.get("tag_keys")
    return tag is not None and isinstance(keys,list) and tag.key in [str(x) for x in keys]


def _matches(reference:object,metric:object,unit:ProcessUnit|None,widgets:list[dict[str,object]],state:dict[str,object])->list[dict[str,object]]:
    ref=str(reference or "").casefold()
    if ref in {"last","previous","τελευταίο","τελευταιο","προηγούμενο","προηγουμενο","αυτό","αυτο"}:
        item=_last(state,widgets); return [item] if item else []
    metric_text=str(metric or "").casefold(); out=[]
    for widget in widgets:
        if unit and str(widget.get("unit_key","")).casefold()!=unit.key.casefold():continue
        hay=" ".join([str(widget.get("id","")),str(widget.get("title","")),*(str(x) for x in (widget.get("tag_keys") or []))]).casefold()
        if (ref and ref not in {"all","null"} and ref in hay) or (metric_text and metric_text in hay):out.append(widget)
    if not out and not metric_text and not ref:
        item=_last(state,widgets); return [item] if item else []
    return out


def _operation_from_legacy(intent:dict[str,Any])->dict[str,Any]:
    unit=intent.get("unit"); metric=intent.get("metric")
    return {"action":intent.get("action"),"units":[unit] if isinstance(unit,str) and unit else [],"metrics":[metric] if isinstance(metric,str) and metric else [],"scope":"explicit" if unit else None,"reference":intent.get("reference"),"widget_type":intent.get("widget_type"),"period":intent.get("period"),"missing":[]}


def _operations(payload:dict[str,Any])->list[dict[str,Any]]:
    raw=payload.get("operations")
    if isinstance(raw,list):return [dict(x) for x in raw if isinstance(x,dict)]
    legacy=payload.get("actions")
    if isinstance(legacy,list):return [_operation_from_legacy(x) for x in legacy if isinstance(x,dict)]
    return [_operation_from_legacy(payload)] if isinstance(payload.get("action"),str) else []


def _compile_operation(op:dict[str,Any],site:SiteModel,state:dict[str,object],working:list[dict[str,object]])->tuple[list[dict[str,object]],dict[str,object]|None,str|None]:
    action=str(op.get("action") or "clarify").casefold(); scope=str(op.get("scope") or "").casefold()
    raw_units=op.get("units"); unit_values=[str(x) for x in raw_units if isinstance(x,str) and x.strip()] if isinstance(raw_units,list) else []
    units=[u for value in unit_values if (u:=_find_unit(site,value)) is not None]
    if scope=="all_units":units=list(site.units)
    raw_metrics=op.get("metrics"); metrics=[str(x) for x in raw_metrics if isinstance(x,str) and x.strip()] if isinstance(raw_metrics,list) else []
    kind=str(op.get("widget_type") or "trend").casefold(); period=str(op.get("period") or "").strip()
    if action in {"answer","clarify"}:return [],dict(op) if action=="clarify" else None,None
    if action=="restore":
        raw=state.get("last_removed_widgets"); restored=[dict(w) for w in raw if isinstance(w,dict)] if isinstance(raw,list) else []
        return ([{"action":"add_widgets","widgets":restored,"read_only":True,"requires_confirmation":False}],None,None) if restored else ([],dict(op),"Δεν έχω προηγούμενα αφαιρεμένα γραφήματα για επαναφορά.")
    if action=="add":
        if not units:return [],{**op,"missing":sorted(set([*(op.get("missing") or []),"units"]))},"Σε ποια μονάδα ή μονάδες το θέλεις;"
        if not metrics:return [],{**op,"missing":sorted(set([*(op.get("missing") or []),"metrics"]))},"Ποια μεταβλητή ή μεταβλητές θέλεις να εμφανίσω;"
        plans=[]; unresolved=[]
        for unit in units:
            for metric in metrics:
                tag=_find_tag(unit,metric)
                if tag is None:unresolved.append(f"{metric} στη {unit.name}")
                else:plans.append({"action":"add_widget","widget":_widget(unit,tag,kind,period or "8h",len(working)+len(plans)),"read_only":True,"requires_confirmation":False})
        if unresolved:return [],dict(op),f"Δεν βρήκα ασφαλή αντιστοίχιση για: {', '.join(unresolved)}."
        return plans,None,None
    if action=="update":
        if not period:return [],{**op,"missing":sorted(set([*(op.get("missing") or []),"period"]))},"Σε ποιο χρονικό εύρος θέλεις να τα αλλάξω;"
        unit_keys={u.key.casefold() for u in units}; candidates=[w for w in working if str(w.get("type","")).casefold()=="trend"]
        if unit_keys:candidates=[w for w in candidates if str(w.get("unit_key","")).casefold() in unit_keys]
        if metrics:candidates=[w for w in candidates if any(_widget_matches_metric(w,m,site) for m in metrics)]
        ref=str(op.get("reference") or "").casefold()
        if ref in {"last","previous"}:
            last=_last(state,candidates); candidates=[last] if last else []
        elif ref and ref not in {"all","null"}:
            candidates=[w for w in candidates if ref in str(w.get("id","")).casefold() or ref in str(w.get("title","")).casefold()]
        if not candidates:return [],dict(op),"Δεν βρήκα υπάρχον γράφημα που να ταιριάζει με αυτό που ζήτησες."
        ids=[str(w.get("id")) for w in candidates if w.get("id")]
        return [{"action":"update_widgets","target_ids":ids,"period":period,"read_only":True,"requires_confirmation":False}],None,None
    unit=units[0] if len(units)==1 else None
    if action=="remove_all":
        ids=[str(w.get("id")) for w in working if w.get("id") and str(w.get("type","")).casefold()=="trend" and (scope=="all_units" or unit is None or str(w.get("unit_key","")).casefold()==unit.key.casefold())]
        return ([{"action":"remove_widgets","target_ids":ids,"read_only":True,"requires_confirmation":False}],None,None) if ids else ([{"action":"answer","read_only":True,"requires_confirmation":False}],None,None)
    if action in {"remove","move"}:
        metric=metrics[0] if len(metrics)==1 else None; hits=_matches(op.get("reference"),metric,None if action=="move" else unit,working,state)
        if len(hits)!=1:return [],{**op,"missing":sorted(set([*(op.get("missing") or []),"reference"]))},"Ποιο ακριβώς γράφημα εννοείς;"
        target=hits[0]
        if action=="remove":return [{"action":"remove_widget","target_id":str(target.get("id")),"read_only":True,"requires_confirmation":False}],None,None
        if unit is None:return [],{**op,"missing":sorted(set([*(op.get("missing") or []),"units"]))},"Σε ποια μονάδα να το μεταφέρω;"
        old=site.find_unit(str(target.get("unit_key",""))); keys=target.get("tag_keys"); oldtag=next((t for t in old.tags if isinstance(keys,list) and keys and t.key==str(keys[0])),None) if old else None
        if oldtag is None:return [],dict(op),"Δεν μπορώ να ταυτοποιήσω με ασφάλεια τη μέτρηση."
        newtag=unit.tag_by_semantic(oldtag.semantic)
        if newtag is None:return [],dict(op),f"Η {unit.name} δεν έχει αντιστοιχισμένη μέτρηση για {oldtag.label}."
        return [{"action":"replace_widget","target_id":str(target.get("id")),"widget":_widget(unit,newtag,str(target.get("type","trend")),str(target.get("period","8h")),0),"read_only":True,"requires_confirmation":False}],None,None
    return [],dict(op),"Δεν έχω αρκετή βεβαιότητα για να εκτελέσω σωστά αυτή την ενέργεια."


def _simulate(widgets:list[dict[str,object]],plan:dict[str,object])->list[dict[str,object]]:
    out=[dict(w) for w in widgets]; action=str(plan.get("action",""))
    if action=="add_widget" and isinstance(plan.get("widget"),dict):out.append(dict(plan["widget"]))
    elif action=="add_widgets" and isinstance(plan.get("widgets"),list):out.extend(dict(w) for w in plan["widgets"] if isinstance(w,dict))
    elif action=="remove_widget":out=[w for w in out if str(w.get("id"))!=str(plan.get("target_id"))]
    elif action=="remove_widgets":
        ids={str(x) for x in plan.get("target_ids",[]) if isinstance(x,(str,int))}; out=[w for w in out if str(w.get("id")) not in ids]
    elif action=="replace_widget" and isinstance(plan.get("widget"),dict):
        tid=str(plan.get("target_id")); out=[dict(plan["widget"]) if str(w.get("id"))==tid else w for w in out]
    elif action=="update_widgets":
        ids={str(x) for x in plan.get("target_ids",[]) if isinstance(x,(str,int))}; period=str(plan.get("period","")).strip()
        out=[({**w,"period":period} if str(w.get("id")) in ids and period else w) for w in out]
    return out


async def plan_with_local_agent(command:str,site:SiteModel,state:dict[str,object],widgets:list[dict[str,object]])->AgentResult|None:
    context={"available_units":_catalog(site),"conversation_state":state,"pending_intent":state.get("pending_intent"),"recent_turns":state.get("recent_turns"),"current_widgets":widgets,"user_command":command}
    try:
        response=await LocalAIClient().generate("Interpret the newest utterance in context. Complete any pending request before creating a new one.",context=context,system_prompt=_AGENT_SYSTEM,temperature=0.05)
        append_trace("agent.raw",{"command":command,"model_text":response.text}); payload=_extract_json(response.text)
    except (LocalAIError,ValueError,json.JSONDecodeError,OSError) as exc:
        append_trace("agent.error",{"command":command,"error":str(exc),"fallback":True}); return None
    operations=_operations(payload)
    if not operations:
        append_trace("agent.compiled",{"command":command,"payload":payload,"result":"fallback:no-operations","fallback":True}); return None
    plans=[]; working=[dict(w) for w in widgets]; pending=None; error=None
    for operation in operations:
        op_plans,op_pending,op_error=_compile_operation(operation,site,state,working)
        if op_pending is not None:pending=op_pending
        if op_error:error=op_error;break
        for plan in op_plans:
            if str(plan.get("action")) not in {"answer","clarify"}:plans.append(plan);working=_simulate(working,plan)
    message=str(payload.get("answer") or "").strip()
    if error or pending:
        text=error or message or "Χρειάζομαι μία ακόμη πληροφορία για να το εκτελέσω σωστά."; final={"action":"clarify","read_only":True,"requires_confirmation":False,"needs_clarification":True,"pending_intent":pending or operations[0]}
        append_trace("agent.compiled",{"command":command,"payload":payload,"compiled_plan":final,"message":text});return AgentResult(final,text)
    if not plans:
        first=str(operations[0].get("action") or "").casefold();final={"action":first if first in {"answer","clarify"} else "answer","read_only":True,"requires_confirmation":False};text=message or "Εντάξει."
        append_trace("agent.compiled",{"command":command,"payload":payload,"compiled_plan":final,"message":text});return AgentResult(final,text)
    final_plan=plans[0] if len(plans)==1 else {"action":"transaction","steps":plans,"read_only":True,"requires_confirmation":False};text=message or (f"Έγινε. Εκτέλεσα {len(plans)} ενέργειες." if len(plans)>1 else "Έγινε.")
    append_trace("agent.compiled",{"command":command,"payload":payload,"compiled_plan":final_plan,"message":text});return AgentResult(final_plan,text)
