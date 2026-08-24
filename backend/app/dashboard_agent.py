from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from .local_ai import LocalAIClient, LocalAIError
from .site_model import ProcessUnit, SiteModel, UnitTag

@dataclass(frozen=True)
class AgentResult:
    plan: dict[str, object]
    message: str

_AGENT_SYSTEM = """You are FCC Assistant, a highly capable refinery dashboard copilot. Understand natural conversational Greek, English, and mixed engineering language like a competent human colleague. Resolve continuity, corrections, ellipsis and pronouns from CONVERSATION STATE and CURRENT WIDGETS. Never invent units, tags, values, alarms or widget ids and never control plant equipment.

Return ONLY JSON, no markdown, using this schema:
{"actions":[{"action":"add|remove|remove_all|move|answer|clarify","unit":"canonical unit key or null","metric":"semantic metric/tag phrase or null","reference":"last|all|widget id|description|null","widget_type":"trend|kpi|average|summary|null","period":"8h|null"}],"answer":"short natural Greek response"}

Rules:
- One utterance may contain several intents. Preserve their spoken order in actions[].
- Explicit newest information overrides older context.
- 'όχι FCC, Hydrocracker', 'έκανες λάθος', 'βάλτο εκεί αντί εδώ' repairs the relevant previous action/widget.
- 'αυτό', 'το προηγούμενο', 'που βάλαμε', 'τελευταίο' refer to the most recently relevant widget unless context clearly identifies another.
- 'όλα τα γραφήματα' => remove_all; explicit unit scopes it, otherwise all trends.
- A request for two metrics means two add actions, not one ambiguous metric.
- Questions are answer actions, not mutations.
- Never silently substitute FCC for HCU/Hydrocracker or another explicit unit.
- Clarify only if materially different executable interpretations remain.
- Keep the final answer concise and natural for speech.
"""

def _extract_json(text: str) -> dict[str, Any]:
    raw=text.strip(); raw=re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I); raw=re.sub(r"\s*```$", "", raw)
    a,b=raw.find("{"),raw.rfind("}")
    if a<0 or b<a: raise ValueError("agent returned no JSON")
    obj=json.loads(raw[a:b+1])
    if not isinstance(obj,dict): raise ValueError("agent response must be object")
    return obj

def _catalog(site: SiteModel)->list[dict[str,object]]:
    return [{"key":u.key,"name":u.name,"aliases":list(u.aliases),"metrics":[{"key":t.key,"label":t.label,"semantic":t.semantic,"aliases":list(t.aliases)} for t in u.tags]} for u in site.units]

def _find_unit(site:SiteModel,v:object)->ProcessUnit|None:
    return site.find_unit(v.strip()) if isinstance(v,str) and v.strip() else None

def _find_tag(unit:ProcessUnit,q:object)->UnitTag|None:
    if not isinstance(q,str) or not q.strip(): return None
    n=q.strip().casefold(); exact=[]; partial=[]
    for t in unit.tags:
        vals=[x.casefold() for x in [t.key,t.label,t.semantic,*t.aliases] if x]
        if n in vals: exact.append(t)
        elif any(n in x or x in n for x in vals): partial.append(t)
    return exact[0] if len(exact)==1 else partial[0] if not exact and len(partial)==1 else None

def _widget(unit:ProcessUnit,tag:UnitTag,kind:str,period:str,order:int)->dict[str,object]:
    kind=kind if kind in {"trend","kpi","average"} else "trend"; width,height=(12,"tall") if kind=="trend" else (4,"compact")
    return {"id":f"{unit.key}-{tag.key}-{uuid.uuid4().hex[:8]}","type":kind,"title":tag.label,"unit_key":unit.key,"tag_keys":[tag.key],"period":period or "8h","layout":{"order":order,"width":width,"height":height}}

def _last(state:dict[str,object],widgets:list[dict[str,object]])->dict[str,object]|None:
    c=state.get("last_widget")
    if isinstance(c,dict):
        cid=str(c.get("id","")); hit=next((w for w in widgets if str(w.get("id",""))==cid),None)
        if hit:return hit
    return widgets[-1] if widgets else None

def _matches(ref:object,metric:object,unit:ProcessUnit|None,widgets:list[dict[str,object]],state:dict[str,object])->list[dict[str,object]]:
    r=str(ref or "").casefold()
    if r in {"last","previous","τελευταίο","τελευταιο","προηγούμενο","προηγουμενο","αυτό","αυτο"}:
        x=_last(state,widgets); return [x] if x else []
    m=str(metric or "").casefold(); out=[]
    for w in widgets:
        if unit and str(w.get("unit_key","" )).casefold()!=unit.key.casefold():continue
        hay=" ".join([str(w.get("id","")),str(w.get("title","")),*(str(x) for x in (w.get("tag_keys") or []))]).casefold()
        if (r and r not in {"all","null"} and r in hay) or (m and m in hay):out.append(w)
    if not out and not m and not r:
        x=_last(state,widgets); return [x] if x else []
    return out

def _compile(intent:dict[str,Any],site:SiteModel,state:dict[str,object],working:list[dict[str,object]])->tuple[dict[str,object]|None,str|None]:
    action=str(intent.get("action") or "clarify").casefold(); unit=_find_unit(site,intent.get("unit")); kind=str(intent.get("widget_type") or "trend").casefold(); period=str(intent.get("period") or "8h")
    if action in {"answer","clarify"}: return {"action":action,"read_only":True,"requires_confirmation":False,"needs_clarification":action=="clarify"},None
    if action=="add":
        if unit is None:
            key=str(state.get("last_requested_unit_key") or state.get("last_unit_key") or ""); unit=site.find_unit(key) if key else None
        if unit is None:return None,"Σε ποια μονάδα το θέλεις;"
        tag=_find_tag(unit,intent.get("metric"))
        if tag is None:return None,f"Ποια μέτρηση θέλεις στη {unit.name};"
        return {"action":"add_widget","widget":_widget(unit,tag,kind,period,len(working)),"read_only":True,"requires_confirmation":False},None
    if action=="remove_all":
        ids=[str(w.get("id")) for w in working if w.get("id") and str(w.get("type","" )).casefold()=="trend" and (unit is None or str(w.get("unit_key","" )).casefold()==unit.key.casefold())]
        return {"action":"remove_widgets","target_ids":ids,"read_only":True,"requires_confirmation":False},None
    if action in {"remove","move"}:
        hits=_matches(intent.get("reference"),intent.get("metric"),None if action=="move" else unit,working,state)
        if len(hits)!=1:return None,"Ποιο ακριβώς γράφημα εννοείς;"
        target=hits[0]
        if action=="remove":return {"action":"remove_widget","target_id":str(target.get("id")),"read_only":True,"requires_confirmation":False},None
        if unit is None:return None,"Σε ποια μονάδα να το μεταφέρω;"
        old=site.find_unit(str(target.get("unit_key",""))); keys=target.get("tag_keys"); oldtag=next((t for t in old.tags if isinstance(keys,list) and keys and t.key==str(keys[0])),None) if old else None
        if oldtag is None:return None,"Δεν μπορώ να ταυτοποιήσω με ασφάλεια τη μέτρηση."
        newtag=unit.tag_by_semantic(oldtag.semantic)
        if newtag is None:return None,f"Η {unit.name} δεν έχει αντιστοιχισμένη μέτρηση για {oldtag.label}."
        return {"action":"replace_widget","target_id":str(target.get("id")),"widget":_widget(unit,newtag,str(target.get("type","trend")),str(target.get("period","8h")),0),"read_only":True,"requires_confirmation":False},None
    return None,"Δεν έχω αρκετή βεβαιότητα για να εκτελέσω σωστά αυτή την ενέργεια."

def _simulate(widgets:list[dict[str,object]],plan:dict[str,object])->list[dict[str,object]]:
    out=[dict(w) for w in widgets]; a=str(plan.get("action",""))
    if a=="add_widget" and isinstance(plan.get("widget"),dict):out.append(dict(plan["widget"]))
    elif a=="remove_widget":out=[w for w in out if str(w.get("id"))!=str(plan.get("target_id"))]
    elif a=="remove_widgets":
        ids={str(x) for x in plan.get("target_ids",[]) if isinstance(x,(str,int))};out=[w for w in out if str(w.get("id")) not in ids]
    elif a=="replace_widget" and isinstance(plan.get("widget"),dict):
        tid=str(plan.get("target_id"));out=[dict(plan["widget"]) if str(w.get("id"))==tid else w for w in out]
    return out

async def plan_with_local_agent(command:str,site:SiteModel,state:dict[str,object],widgets:list[dict[str,object]])->AgentResult|None:
    context={"available_units":_catalog(site),"conversation_state":state,"current_widgets":widgets,"user_command":command}
    try:
        response=await LocalAIClient().generate("Interpret the newest utterance and produce the complete ordered action plan.",context=context,system_prompt=_AGENT_SYSTEM,temperature=0.05); payload=_extract_json(response.text)
    except (LocalAIError,ValueError,json.JSONDecodeError):return None
    raw=payload.get("actions"); intents=[x for x in raw if isinstance(x,dict)] if isinstance(raw,list) else []
    if not intents and isinstance(payload.get("action"),str):intents=[payload]
    if not intents:return AgentResult({"action":"clarify","read_only":True,"needs_clarification":True},"Δεν κατάλαβα αρκετά καθαρά την εντολή.")
    plans=[]; working=[dict(w) for w in widgets]
    for intent in intents:
        plan,error=_compile(intent,site,state,working)
        if error:return AgentResult({"action":"clarify","read_only":True,"needs_clarification":True},error)
        if plan and str(plan.get("action")) not in {"answer","clarify"}:
            plans.append(plan);working=_simulate(working,plan)
    message=str(payload.get("answer") or "").strip() or ("Έγινε." if plans else "Εντάξει.")
    if not plans:return AgentResult({"action":"answer","read_only":True,"requires_confirmation":False},message)
    if len(plans)==1:return AgentResult(plans[0],message)
    return AgentResult({"action":"transaction","steps":plans,"read_only":True,"requires_confirmation":False},message)
