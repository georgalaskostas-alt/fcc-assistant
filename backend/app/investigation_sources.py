"""Canonical, deduplicated evidence/source view for engineering investigations."""
from __future__ import annotations
from typing import Any
from .investigation_evidence import evidence_identity

def _kind(item:dict[str,Any],fallback:str="evidence")->str:
    tool=str(item.get("tool") or "")
    return {"get_history":"historian","search_tags":"tag_catalog","search_archive":"technical_archive","search_alarms_events":"alarms_events","find_similar_episodes":"previous_incident"}.get(tool,tool or fallback)

def _normalize(item:dict[str,Any],origin:str,fallback:str)->dict[str,Any]:
    data=item.get("data") if isinstance(item.get("data"),dict) else {}
    return {"evidence_id":str(item.get("stable_evidence_id") or item.get("evidence_id") or evidence_identity(item)),"source_kind":_kind(item,fallback),"tool":item.get("tool"),"description":item.get("description") or data.get("title") or data.get("name"),"provenance":dict(item.get("provenance") or {}),"origin":origin,"data":data}

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


def canonical_source_ids(sources:list[dict[str,Any]])->set[str]:
    return {str(source.get("evidence_id")) for source in sources if isinstance(source,dict) and source.get("evidence_id")}

def resolve_source_ids(refs:list[Any],sources:list[dict[str,Any]])->list[str]:
    """Resolve claim/evidence references only to canonical source IDs."""
    valid=canonical_source_ids(sources);resolved=[]
    for ref in refs:
        if isinstance(ref,dict):
            value=ref.get("stable_evidence_id") or ref.get("evidence_id") or ref.get("id")
        else:value=ref
        if value is None:continue
        key=str(value)
        if key in valid and key not in resolved:resolved.append(key)
    return resolved


def source_drilldown(source:dict[str,Any])->dict[str,Any]:
    """Return a bounded, read-only detail view suitable for engineer inspection."""
    kind=str(source.get("source_kind") or "evidence");data=dict(source.get("data") or {});prov=dict(source.get("provenance") or {})
    detail={"evidence_id":source.get("evidence_id"),"source_kind":kind,"description":source.get("description"),"provenance":prov,"read_only":True}
    if kind=="historian":
        detail["historian"]={"tag_key":prov.get("tag_key") or data.get("tag_key"),"start_time":prov.get("start_time") or data.get("start_time"),"end_time":prov.get("end_time") or data.get("end_time"),"points":data.get("points") or data.get("items") or []}
    elif kind=="technical_archive":
        detail["document"]={"document_id":prov.get("document_id") or data.get("document_id"),"revision":prov.get("revision") or data.get("revision"),"page":prov.get("page") or data.get("page"),"title":data.get("title"),"status":data.get("status"),"excerpt":data.get("text") or data.get("excerpt"),"record_id":prov.get("record_id") or data.get("record_id"),"source_path":prov.get("source_path") or data.get("source_path"),"open_target":{"record_id":prov.get("record_id") or data.get("record_id"),"document_id":prov.get("document_id") or data.get("document_id"),"revision":prov.get("revision") or data.get("revision"),"page":prov.get("page") or data.get("page")}}
    elif kind=="alarms_events":
        detail["event"]={"event_id":prov.get("event_id") or data.get("event_id"),"timestamp":data.get("timestamp") or data.get("time"),"tag_key":data.get("tag_key"),"message":data.get("message") or data.get("description"),"state":data.get("state")}
    elif kind=="previous_incident":
        detail["incident"]={"episode_id":prov.get("episode_id") or data.get("episode_id") or data.get("id"),"title":data.get("title") or data.get("name"),"start_time":data.get("start_time"),"end_time":data.get("end_time"),"summary":data.get("summary") or data.get("description")}
    else:detail["evidence"]=data
    return detail
