"""Canonical, deduplicated evidence/source view for engineering investigations."""
from __future__ import annotations
from typing import Any
from .investigation_evidence import evidence_identity

def _kind(item:dict[str,Any],fallback:str="evidence")->str:
    tool=str(item.get("tool") or "")
    return {"get_history":"historian","search_tags":"tag_catalog","search_archive":"technical_archive","search_alarms_events":"alarms_events","find_similar_episodes":"previous_incident"}.get(tool,tool or fallback)

def _normalize(item:dict[str,Any],origin:str,fallback:str)->dict[str,Any]:
    data=item.get("data") if isinstance(item.get("data"),dict) else {}
    return {"evidence_id":str(item.get("stable_evidence_id") or item.get("evidence_id") or evidence_identity(item)),"source_kind":_kind(item,fallback),"tool":item.get("tool"),"description":item.get("description") or data.get("title") or data.get("name"),"provenance":dict(item.get("provenance") or {}),"origin":origin}

def collect_canonical_sources(synthesis:dict[str,Any])->list[dict[str,Any]]:
    collected=[];seen=set()
    def add(item:dict[str,Any],origin:str,fallback:str="evidence")->None:
        source=_normalize(item,origin,fallback);key=source["evidence_id"]
        if key in seen:return
        seen.add(key);collected.append(source)
    for field in ("evidence_package","discovery_evidence"):
        for item in synthesis.get(field) or []:
            if isinstance(item,dict):add(item,field)
    for field,kind in (("archive_evidence","technical_archive"),("event_evidence","alarms_events"),("similar_episodes","previous_incident"),("history_evidence","historian")):
        value=synthesis.get(field)
        rows=(value.get("items") or value.get("hits") or value.get("evidence") or []) if isinstance(value,dict) else value
        if isinstance(rows,list):
            for item in rows:
                if isinstance(item,dict):add(item,field,kind)
    return collected
