"""Turn bounded semantic neighborhoods into governed evidence-discovery suggestions."""
from __future__ import annotations
from typing import Any

def semantic_discovery_candidates(*, neighborhood:dict[str,Any], synthesis:dict[str,Any], limit:int=4)->list[dict[str,Any]]:
    resolved={str(x) for x in synthesis.get("resolved_tags") or []}
    discovered={
        str(row.get("key") or row.get("tag_key") or "")
        for row in ((synthesis.get("discovered_tags") or {}).get("items") or [])
        if isinstance(row,dict)
    }
    candidates=[]
    for node in neighborhood.get("nodes",[]):
        if not isinstance(node,dict):continue
        if node.get("kind")=="tag":
            key=str(node.get("tag_key") or "").strip()
            if key and key not in resolved and key not in discovered:
                candidates.append({"kind":"measurement","tag_key":key,"query":str(node.get("label") or key),"reason":"Semantically adjacent governed measurement has not been investigated."})
        elif node.get("kind")=="equipment":
            key=str(node.get("equipment_key") or "").strip()
            if key:candidates.append({"kind":"equipment","equipment_key":key,"query":str(node.get("label") or key),"reason":"Adjacent equipment may have approved technical context relevant to the hypothesis."})
    unique=[];seen=set()
    for item in candidates:
        fingerprint=(item["kind"],item.get("tag_key") or item.get("equipment_key"))
        if fingerprint in seen:continue
        seen.add(fingerprint);unique.append(item)
    return unique[:max(0,limit)]

def semantic_candidates_to_actions(*, candidates:list[dict[str,Any]], unit_key:str)->list[dict[str,Any]]:
    actions=[]
    for item in candidates:
        if item.get("kind")=="measurement":
            actions.append({"tool":"search_tags","value":6,"reason":item["reason"],"arguments":{"query":item["query"]},"semantic_candidate":item})
        elif item.get("kind")=="equipment":
            actions.append({"tool":"search_archive","value":5,"reason":item["reason"],"arguments":{"query":item["query"],"unit_key":unit_key,"equipment_key":item["equipment_key"],"limit":6,"approved_only":True},"semantic_candidate":item})
    return actions
