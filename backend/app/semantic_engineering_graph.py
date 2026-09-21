"""Refinery semantic engineering graph and bounded graph traversal."""
from __future__ import annotations
from typing import Any
from .site_model import SiteModel

def _equipment_for_semantic(semantic:str)->tuple[str,str]:
    value=semantic.casefold()
    if "regenerator" in value:return ("regenerator","Regenerator")
    if "fractionator" in value:return ("main_fractionator","Main Fractionator")
    if "reactor" in value or "reaction" in value:return ("reactor","Reactor")
    return ("unit_process","Unit Process")

def _section_for_equipment(equipment:str)->tuple[str,str]:
    if equipment in {"regenerator","reactor"}:return ("reaction_regeneration","Reaction & Regeneration")
    if equipment=="main_fractionator":return ("fractionation","Fractionation")
    return ("general","General Process")

def build_semantic_engineering_graph(*, unit_key:str, site:SiteModel, hypotheses:list[dict[str,Any]], evidence_graph:dict[str,Any]) -> dict[str,Any]:
    unit=site.find_unit(unit_key);nodes=[];edges=[];seen=set();edge_seen=set()
    def node(identifier:str,kind:str,label:str,**meta:Any)->None:
        if identifier in seen:return
        seen.add(identifier);nodes.append({"id":identifier,"kind":kind,"label":label,**meta})
    def edge(source:str,target:str,relation:str)->None:
        key=(source,target,relation)
        if source and target and key not in edge_seen:edge_seen.add(key);edges.append({"from":source,"to":target,"relation":relation})
    refinery_id="refinery:site";uid=f"unit:{unit_key}"
    node(refinery_id,"refinery",site.name);node(uid,"unit",unit.name if unit else unit_key);edge(uid,refinery_id,"belongs_to_refinery")
    if unit:
        configured_sections={section.key:section for section in unit.sections}
        configured_equipment={item.key:item for item in unit.equipment}
        for section in unit.sections:
            sid=f"section:{unit_key}:{section.key}";node(sid,"section",section.name,section_key=section.key);edge(sid,uid,"belongs_to_unit")
        for item in unit.equipment:
            eid=f"equipment:{unit_key}:{item.key}";node(eid,"equipment",item.name,equipment_key=item.key,equipment_type=item.equipment_type)
            if item.section_key:
                sid=f"section:{unit_key}:{item.section_key}"
                if item.section_key not in configured_sections:node(sid,"section",item.section_key,section_key=item.section_key)
                edge(eid,sid,"belongs_to_section")
        for stream in unit.streams:
            stream_id=f"stream:{unit_key}:{stream.key}";node(stream_id,"stream",stream.name,stream_key=stream.key,engineering_relationships=list(stream.relationships))
            if stream.from_equipment:edge(f"equipment:{unit_key}:{stream.from_equipment}",stream_id,"feeds_stream")
            if stream.to_equipment:edge(stream_id,f"equipment:{unit_key}:{stream.to_equipment}","feeds_equipment")
        def configured_node_id(kind:str,key:str)->str:
            return {
                "equipment":f"equipment:{unit_key}:{key}",
                "stream":f"stream:{unit_key}:{key}",
                "section":f"section:{unit_key}:{key}",
                "measurement":f"measurement:{key}",
                "tag":f"tag:{key}",
            }.get(kind,f"{kind}:{unit_key}:{key}")
        for relationship in unit.relationships:
            source=configured_node_id(relationship.source_kind,relationship.source_key)
            target=configured_node_id(relationship.target_kind,relationship.target_key)
            edge(source,target,relationship.relation)
            if relationship.bidirectional:edge(target,source,relationship.relation)
        for tag in unit.tags:
            tid=f"tag:{tag.key}";mid=f"measurement:{tag.semantic}"
            equipment_key=tag.equipment_key
            if equipment_key and equipment_key in configured_equipment:
                equipment_label=configured_equipment[equipment_key].name
            elif equipment_key:
                equipment_label=equipment_key
            else:
                equipment_key,equipment_label=_equipment_for_semantic(tag.semantic)
            eid=f"equipment:{unit_key}:{equipment_key}"
            if equipment_key not in configured_equipment:
                section_key,section_label=_section_for_equipment(equipment_key);sid=f"section:{unit_key}:{section_key}"
                node(eid,"equipment",equipment_label,equipment_key=equipment_key);node(sid,"section",section_label,section_key=section_key);edge(eid,sid,"belongs_to_section");edge(sid,uid,"belongs_to_unit")
            node(tid,"tag",tag.label,engineering_unit=tag.unit,tag_key=tag.key)
            node(mid,"measurement",tag.semantic,semantic_key=tag.semantic)
            edge(tid,mid,"measures");edge(mid,eid,"measurement_of")
            if tag.stream_key:
                stream_id=f"stream:{unit_key}:{tag.stream_key}"
                edge(mid,stream_id,"measurement_of_stream")
    for item in evidence_graph.get("nodes",[]):
        if not isinstance(item,dict):continue
        eid=str(item.get("id") or "");kind=str(item.get("kind") or "")
        if kind=="evidence":
            source_kind=str(item.get("source_kind") or "evidence")
            node(eid,"evidence",str(item.get("label") or eid),source_kind=source_kind,provenance=item.get("provenance") or {})
            provenance=item.get("provenance") if isinstance(item.get("provenance"),dict) else {}
            tag_key=str(provenance.get("tag_key") or "")
            equipment_key=str(provenance.get("equipment_key") or "")
            if tag_key and f"tag:{tag_key}" in seen:edge(eid,f"tag:{tag_key}","derived_from")
            if equipment_key and f"equipment:{unit_key}:{equipment_key}" in seen:edge(eid,f"equipment:{unit_key}:{equipment_key}","documents")
            if source_kind=="technical_archive":edge(eid,uid,"document_for_unit")
            elif source_kind=="previous_incident":edge(eid,uid,"incident_in_unit")
            elif source_kind=="alarms_events":edge(eid,uid,"event_in_unit")
        elif kind=="hypothesis":node(eid,"hypothesis",str(item.get("label") or eid),causal_status="not_established")
    for relation in evidence_graph.get("edges",[]):
        if isinstance(relation,dict):edge(str(relation.get("from") or ""),str(relation.get("to") or ""),str(relation.get("relation") or "related"))
    for hypothesis in hypotheses:
        if not isinstance(hypothesis,dict):continue
        hid=str(hypothesis.get("id") or "");statement=str(hypothesis.get("statement") or "").casefold()
        if not hid:continue
        for tag in unit.tags if unit else ():
            tokens={tag.key.casefold(),tag.semantic,*[a.casefold() for a in tag.aliases]}
            if any(token and token in statement for token in tokens):edge(f"measurement:{tag.semantic}",hid,"investigated_in")
    return {"unit_key":unit_key,"nodes":nodes,"edges":edges,"read_only":True,"causal_inference":False}

def traverse_semantic_neighbors(*, graph:dict[str,Any], start_ids:list[str], max_depth:int=2, max_nodes:int=24) -> dict[str,Any]:
    """Return a bounded, deterministic neighborhood; this discovers context, not causality."""
    nodes={str(n.get("id")):n for n in graph.get("nodes",[]) if isinstance(n,dict) and n.get("id")}
    adjacency:dict[str,list[tuple[str,str]]]={}
    for e in graph.get("edges",[]):
        if not isinstance(e,dict):continue
        a,b,r=str(e.get("from") or ""),str(e.get("to") or ""),str(e.get("relation") or "related")
        if a and b:
            adjacency.setdefault(a,[]).append((b,r));adjacency.setdefault(b,[]).append((a,r))
    visited=set(x for x in start_ids if x in nodes);frontier=[(x,0) for x in visited];paths=[]
    while frontier and len(visited)<max_nodes:
        current,depth=frontier.pop(0)
        if depth>=max_depth:continue
        for neighbor,relation in adjacency.get(current,[]):
            paths.append({"from":current,"to":neighbor,"relation":relation,"depth":depth+1})
            if neighbor not in visited and len(visited)<max_nodes:
                visited.add(neighbor);frontier.append((neighbor,depth+1))
    return {"start_ids":[x for x in start_ids if x in nodes],"nodes":[nodes[x] for x in visited],"paths":paths,"max_depth":max_depth,"bounded":True,"causal_inference":False}


def trace_process_paths(*, graph:dict[str,Any], start_ids:list[str], max_depth:int=4, max_paths:int=24)->dict[str,Any]:
    """Traverse directed engineering paths. Relationship edges express configured context, never proven causality."""
    allowed={"feeds_stream","feeds_equipment","upstream_of","downstream_of","pressure_influence","temperature_influence","flow_influence","heat_influence","material_flow","signal_context"}
    adjacency:dict[str,list[tuple[str,str]]]={}
    for item in graph.get("edges",[]):
        if not isinstance(item,dict):continue
        source,target,relation=str(item.get("from") or ""),str(item.get("to") or ""),str(item.get("relation") or "")
        if source and target and relation in allowed:adjacency.setdefault(source,[]).append((target,relation))
    paths=[];queue=[(start,[start],[]) for start in start_ids]
    while queue and len(paths)<max_paths:
        current,nodes,relations=queue.pop(0)
        if len(relations)>=max_depth:continue
        for target,relation in adjacency.get(current,[]):
            if target in nodes:continue
            new_nodes=nodes+[target];new_relations=relations+[relation]
            paths.append({"nodes":new_nodes,"relationships":new_relations,"depth":len(new_relations),"causal_status":"not_established"})
            queue.append((target,new_nodes,new_relations))
            if len(paths)>=max_paths:break
    return {"start_ids":start_ids,"paths":paths,"bounded":True,"directed":True,"causal_inference":False}
