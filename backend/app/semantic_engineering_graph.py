"""Refinery semantic engineering relationships for source-grounded investigations."""
from __future__ import annotations
from typing import Any
from .site_model import SiteModel

def build_semantic_engineering_graph(*, unit_key:str, site:SiteModel, hypotheses:list[dict[str,Any]], evidence_graph:dict[str,Any]) -> dict[str,Any]:
    unit=site.find_unit(unit_key);nodes=[];edges=[];seen=set()
    def node(identifier:str,kind:str,label:str,**meta:Any)->None:
        if identifier in seen:return
        seen.add(identifier);nodes.append({"id":identifier,"kind":kind,"label":label,**meta})
    def edge(source:str,target:str,relation:str)->None:
        if source and target:edges.append({"from":source,"to":target,"relation":relation})
    uid=f"unit:{unit_key}";node(uid,"unit",unit.name if unit else unit_key)
    if unit:
        for tag in unit.tags:
            tid=f"tag:{tag.key}";sid=f"measurement:{tag.semantic}"
            node(tid,"tag",tag.label,engineering_unit=tag.unit,tag_key=tag.key)
            node(sid,"measurement",tag.semantic,semantic_key=tag.semantic)
            edge(tid,sid,"measures");edge(sid,uid,"belongs_to_unit")
    for item in evidence_graph.get("nodes",[]):
        if not isinstance(item,dict):continue
        eid=str(item.get("id") or "");kind=str(item.get("kind") or "")
        if kind=="evidence":
            node(eid,"evidence",str(item.get("label") or eid),source_kind=item.get("source_kind"),provenance=item.get("provenance") or {})
            provenance=item.get("provenance") if isinstance(item.get("provenance"),dict) else {}
            tag_key=str(provenance.get("tag_key") or "")
            if tag_key and f"tag:{tag_key}" in seen:edge(eid,f"tag:{tag_key}","derived_from")
        elif kind=="hypothesis":
            node(eid,"hypothesis",str(item.get("label") or eid),causal_status="not_established")
    for relation in evidence_graph.get("edges",[]):
        if isinstance(relation,dict):edge(str(relation.get("from") or ""),str(relation.get("to") or ""),str(relation.get("relation") or "related"))
    for hypothesis in hypotheses:
        if not isinstance(hypothesis,dict):continue
        hid=str(hypothesis.get("id") or "")
        statement=str(hypothesis.get("statement") or "").casefold()
        if not hid:continue
        for tag in unit.tags if unit else ():
            tokens={tag.key.casefold(),tag.semantic,*[a.casefold() for a in tag.aliases]}
            if any(token and token in statement for token in tokens):
                edge(f"measurement:{tag.semantic}",hid,"investigated_in")
    return {"unit_key":unit_key,"nodes":nodes,"edges":edges,"read_only":True,"causal_inference":False}
