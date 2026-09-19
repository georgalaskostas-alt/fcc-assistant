"""Resolve natural-language references to durable investigations.

Resolution is deterministic and user-scoped. It prefers recent non-failed work,
matches unit/topic terms, and returns ambiguity instead of guessing.
"""
from __future__ import annotations
import re
from typing import Any
from .investigation_store import Investigation, InvestigationStore, InvestigationStatus

_STOP={"continue","resume","investigation","research","the","that","about","for","with","συνέχισε","συνεχισε","έρευνα","ερευνα","εκείνο","εκεινο","θέμα","θεμα","με","το","τη","την","για"}

def _terms(text:str)->set[str]:
    return {x.casefold() for x in re.findall(r"[A-Za-zΑ-Ωα-ωΆ-ώ0-9_.-]{2,}",text) if x.casefold() not in _STOP}

def resolve_investigation_reference(*, store:InvestigationStore,user_id:str,utterance:str,unit_key:str|None=None,limit:int=8)->dict[str,Any]:
    query=_terms(utterance)
    candidates=[]
    for item in store.list(user_id=user_id)[:limit]:
        if item.status==InvestigationStatus.FAILED: continue
        hay=_terms(item.goal+" "+str(item.resume_context.get("last_autonomous_focus") or ""))
        overlap=sorted(query & hay)
        unit_match=bool(unit_key and item.unit_key==unit_key.casefold())
        score=len(overlap)*3+(2 if unit_match else 0)+(1 if item.status in {InvestigationStatus.WAITING,InvestigationStatus.RUNNING} else 0)
        if score: candidates.append((score,item,overlap))
    candidates.sort(key=lambda x:(x[0],x[1].updated_at),reverse=True)
    if not candidates: return {"status":"not_found","investigation":None,"candidates":[]}
    top=candidates[0]
    tied=[x for x in candidates if x[0]==top[0]]
    packed=[{"id":x[1].id,"goal":x[1].goal,"unit_key":x[1].unit_key,"status":x[1].status.value,"score":x[0],"matched_terms":x[2]} for x in candidates[:5]]
    if len(tied)>1: return {"status":"ambiguous","investigation":None,"candidates":packed}
    return {"status":"resolved","investigation":packed[0],"candidates":packed}
