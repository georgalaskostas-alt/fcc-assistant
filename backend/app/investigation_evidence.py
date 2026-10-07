"""Stable evidence identity and novelty handling for investigation rounds."""
from __future__ import annotations
import hashlib,json
from typing import Any

def _stable(value:Any)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),default=str)

def evidence_identity(item:dict[str,Any])->str:
    tool=str(item.get("tool") or "")
    data=item.get("data") if isinstance(item.get("data"),dict) else {}
    provenance=item.get("provenance") if isinstance(item.get("provenance"),dict) else {}
    if tool=="search_archive":
        key=data.get("record_id") or data.get("document_id") or provenance.get("record_id")
        rev=data.get("revision") or provenance.get("revision")
        page=data.get("page") or provenance.get("page")
        if key:return f"archive:{key}:{rev or ''}:{page or ''}"
    if tool=="search_alarms_events":
        key=data.get("event_id") or data.get("id")
        if key:return f"event:{key}"
    if tool=="find_similar_episodes":
        key=data.get("episode_id") or data.get("id")
        if key:return f"episode:{key}"
    if tool=="get_history":
        tag_meta=data.get("tag") if isinstance(data.get("tag"),dict) else {}
        range_meta=data.get("range") if isinstance(data.get("range"),dict) else {}
        tag=data.get("tag_key") or tag_meta.get("key") or tag_meta.get("tag_key") or provenance.get("tag_key")
        start=data.get("start_time") or range_meta.get("start_time") or provenance.get("start_time")
        end=data.get("end_time") or range_meta.get("end_time") or provenance.get("end_time")
        if tag:return f"history:{tag}:{start or ''}:{end or ''}"
    payload={"tool":tool,"data":data,"provenance":provenance}
    return "evidence:"+hashlib.sha256(_stable(payload).encode("utf-8")).hexdigest()[:24]

def _usable_rows(item:dict[str,Any])->list[Any]:
    """Return concrete evidence rows; successful empty search wrappers are not evidence."""
    tool=str(item.get("tool") or "")
    data=item.get("data")
    if tool=="search_archive":
        if isinstance(data,list):return data
        if isinstance(data,dict):
            rows=data.get("hits",data.get("items",[]))
            return rows if isinstance(rows,list) else []
        return []
    if tool=="search_alarms_events":
        if isinstance(data,list):return data
        if isinstance(data,dict):
            rows=data.get("events",data.get("hits",data.get("items",[])))
            return rows if isinstance(rows,list) else []
        return []
    if tool=="find_similar_episodes":
        if isinstance(data,list):return data
        if isinstance(data,dict):
            rows=data.get("episodes",data.get("hits",data.get("items",[])))
            return rows if isinstance(rows,list) else []
        return []
    return [data] if data is not None else []

def is_usable_evidence(item:dict[str,Any])->bool:
    tool=str(item.get("tool") or "")
    if tool in {"search_archive","search_alarms_events","find_similar_episodes"}:
        return bool(_usable_rows(item))
    return True

def merge_new_evidence(existing:list[dict[str,Any]],incoming:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    seen={evidence_identity(x) for x in existing if isinstance(x,dict)}
    merged=list(existing);new=[]
    for item in incoming:
        if not isinstance(item,dict) or not is_usable_evidence(item):continue
        identity=evidence_identity(item)
        if identity in seen:continue
        enriched=dict(item);enriched["stable_evidence_id"]=identity
        seen.add(identity);merged.append(enriched);new.append(enriched)
    return merged,new
