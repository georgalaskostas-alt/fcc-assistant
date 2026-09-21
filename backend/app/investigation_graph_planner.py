"""Turn bounded semantic neighborhoods into governed evidence-discovery suggestions."""
from __future__ import annotations
from typing import Any
from .investigation_value import path_feedback_index

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
            actions.append({"tool":"search_tags","value":int(round(float(item.get("adaptive_value") or 6))),"reason":item["reason"],"arguments":{"query":item["query"]},"semantic_candidate":item,"hypothesis_branch_id":item.get("hypothesis_branch_id")})
        elif item.get("kind")=="equipment":
            actions.append({"tool":"search_archive","value":int(round(float(item.get("adaptive_value") or 5))),"reason":item["reason"],"arguments":{"query":item["query"],"unit_key":unit_key,"equipment_key":item["equipment_key"],"limit":6,"approved_only":True},"semantic_candidate":item,"hypothesis_branch_id":item.get("hypothesis_branch_id")})
    return actions


def process_path_candidates(*, process_paths:dict[str,Any], graph:dict[str,Any], synthesis:dict[str,Any], limit:int=4)->list[dict[str,Any]]:
    """Rank unseen measurements/equipment reached through configured process paths."""
    nodes={str(n.get("id")):n for n in graph.get("nodes",[]) if isinstance(n,dict)}
    resolved={str(x) for x in synthesis.get("resolved_tags") or []};candidates=[]
    for path in process_paths.get("paths",[]):
        if not isinstance(path,dict):continue
        relations=list(path.get("relationships") or [])
        for node_id in reversed(list(path.get("nodes") or [])):
            node=nodes.get(str(node_id),{})
            if node.get("kind")=="equipment":
                candidates.append({"kind":"equipment","equipment_key":node.get("equipment_key"),"query":node.get("label"),"path_relationships":relations,"reason":"Reached through configured process-path relationships; inspect approved engineering context."});break
            if node.get("kind")=="tag" and str(node.get("tag_key") or "") not in resolved:
                candidates.append({"kind":"measurement","tag_key":node.get("tag_key"),"query":node.get("label"),"path_relationships":relations,"reason":"Reached through configured process-path relationships; inspect governed measurement."});break
    feedback=path_feedback_index(list(synthesis.get("process_path_information_gain") or []))
    unique=[];seen=set()
    for item in candidates:
        fp=(item["kind"],item.get("tag_key") or item.get("equipment_key"))
        if fp in seen or not fp[1]:continue
        seen.add(fp)
        history=feedback.get((str(fp[1]),tuple(str(x) for x in item.get("path_relationships") or [])),{})
        if int(history.get("no_gain") or 0)>=1 and int(history.get("useful") or 0)==0:continue
        item["prior_path_attempts"]=int(history.get("attempts") or 0)
        item["prior_path_mean_gain"]=float(history.get("mean_score") or 0.0)
        item["adaptive_value"]=round(6.0+min(3.0,item["prior_path_mean_gain"])-min(3,item["prior_path_attempts"])*0.5,3)
        unique.append(item)
    unique.sort(key=lambda x:(-float(x.get("adaptive_value") or 0.0),str(x.get("equipment_key") or x.get("tag_key") or "")))
    return unique[:max(0,limit)]


def branch_process_path_candidates(*, hypotheses:list[dict[str,Any]], graph:dict[str,Any], synthesis:dict[str,Any], trace_fn, limit_per_branch:int=2)->list[dict[str,Any]]:
    """Discover process-path evidence separately for each active hypothesis branch."""
    all_candidates=[]
    for hypothesis in hypotheses:
        if not isinstance(hypothesis,dict):continue
        branch_id=str(hypothesis.get("id") or "")
        if not branch_id:continue
        neighborhood_nodes=[]
        for edge in graph.get("edges",[]):
            if not isinstance(edge,dict):continue
            if str(edge.get("to") or "")==branch_id:neighborhood_nodes.append(str(edge.get("from") or ""))
            if str(edge.get("from") or "")==branch_id:neighborhood_nodes.append(str(edge.get("to") or ""))
        starts=[]
        nodes={str(n.get("id")):n for n in graph.get("nodes",[]) if isinstance(n,dict)}
        for node_id in neighborhood_nodes:
            node=nodes.get(node_id,{})
            if node.get("kind") in {"equipment","stream"} and node_id not in starts:starts.append(node_id)
        paths=trace_fn(graph=graph,start_ids=starts[:4],max_depth=4,max_paths=16)
        candidates=process_path_candidates(process_paths=paths,graph=graph,synthesis=synthesis,limit=limit_per_branch)
        for candidate in candidates:
            item=dict(candidate);item["hypothesis_branch_id"]=branch_id
            item["hypothesis_statement"]=str(hypothesis.get("statement") or "")
            all_candidates.append(item)
    return all_candidates
