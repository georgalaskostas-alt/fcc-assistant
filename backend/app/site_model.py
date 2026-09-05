from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass(frozen=True)
class UnitTag:
    key:str; label:str; unit:str; aliases:tuple[str,...]=(); semantic_key:str=""
    @property
    def semantic(self)->str:return (self.semantic_key or self.key).strip().casefold()
@dataclass(frozen=True)
class ProcessUnit:
    key:str; name:str; tags:tuple[UnitTag,...]=(); aliases:tuple[str,...]=()
    def tag_by_semantic(self,semantic_key:str)->UnitTag|None:
        needle=semantic_key.strip().casefold();return next((t for t in self.tags if t.semantic==needle),None)
    def matches(self,query:str)->bool:
        needle=query.strip().casefold();return needle in {self.key.casefold(),self.name.casefold(),*(a.casefold() for a in self.aliases)}
@dataclass(frozen=True)
class SiteModel:
    name:str; units:tuple[ProcessUnit,...]=()
    def list_units(self)->list[dict[str,object]]:return [asdict(u) for u in self.units]
    def find_unit(self,query:str)->ProcessUnit|None:return next((u for u in self.units if u.matches(query)),None)
    def resolve_tag(self,unit_key:str,query:str)->UnitTag|None:
        unit=self.find_unit(unit_key)
        if unit is None:return None
        needle=query.strip().casefold()
        return next((t for t in unit.tags if needle in {t.key.casefold(),t.label.casefold(),t.semantic,*(a.casefold() for a in t.aliases)}),None)

def _common_tags(prefix:str="")->tuple[UnitTag,...]:
    p=f"{prefix}_" if prefix else ""
    return (
        UnitTag(f"{p}feed_flow","Feed Flow","m3/h",("feed","τροφοδοσία","τροφοδοσια"),"feed_flow"),
        UnitTag(f"{p}reactor_temp","Reactor Temperature","C",("reactor temperature","reaction temperature","θερμοκρασία reactor","θερμοκρασια reactor","θερμοκρασία αντίδρασης","θερμοκρασια αντιδρασης"),"reaction_temperature"),
    )

def default_site_model()->SiteModel:
    # Safe development/demo semantic catalog. It contains no PI WebIds, hosts, credentials or real plant metadata.
    # Real tags still come exclusively from FCC_SITE_CONFIG when configured.
    return SiteModel("Refinery",(
        ProcessUnit("fcc","FCC",_common_tags()+(
            UnitTag("regenerator_temp","Regenerator Temperature","C",("regenerator temperature","θερμοκρασία regenerator","θερμοκρασια regenerator"),"regenerator_temperature"),
            UnitTag("regenerator_o2","Regenerator O2","%",("o2","οξυγόνο regenerator","οξυγονο regenerator"),"regenerator_o2"),
            UnitTag("fractionator_dp","Main Fractionator DP","bar",("fractionator dp","dp fractionator"),"fractionator_dp"),
            UnitTag("naphtha_rate","Naphtha Rate","m3/h",("naphtha","νάφθα","ναφθα"),"naphtha_rate"),
            UnitTag("lcco_rate","LCCO Rate","m3/h",("lcco",),"lcco_rate"),
        ),("fluid catalytic cracking",)),
        ProcessUnit("hcu","Hydrocracker",_common_tags("hcu"),("hydrocracker","hydro cracker","hydrocracking","hydro cracking","υδροκράκερ","υδροκρακερ","hcu")),
    ))

def _site_from_payload(payload:dict[str,object])->SiteModel:
    name=str(payload.get("name") or "Refinery").strip() or "Refinery";raw_units=payload.get("units")
    if not isinstance(raw_units,list) or not raw_units:raise ValueError("Site configuration must contain at least one unit")
    units=[];seen_units=set()
    for raw_unit in raw_units:
        if not isinstance(raw_unit,dict):raise ValueError("Each site unit must be an object")
        key=str(raw_unit.get("key") or "").strip().casefold();unit_name=str(raw_unit.get("name") or key).strip();aliases=raw_unit.get("aliases") or []
        if not isinstance(aliases,list):raise ValueError(f"Aliases for unit {key or unit_name} must be a list")
        if not key or key in seen_units:raise ValueError("Each unit requires a unique non-empty key")
        seen_units.add(key);raw_tags=raw_unit.get("tags") or []
        if not isinstance(raw_tags,list):raise ValueError(f"Unit {key} tags must be a list")
        tags=[];seen_tags=set()
        for raw_tag in raw_tags:
            if not isinstance(raw_tag,dict):raise ValueError(f"Unit {key} contains an invalid tag definition")
            tag_key=str(raw_tag.get("key") or "").strip();label=str(raw_tag.get("label") or tag_key).strip();engineering_unit=str(raw_tag.get("unit") or "").strip();tag_aliases=raw_tag.get("aliases") or [];semantic=str(raw_tag.get("semantic_key") or tag_key).strip().casefold()
            if not isinstance(tag_aliases,list):raise ValueError(f"Aliases for {key}.{tag_key} must be a list")
            if not tag_key or tag_key in seen_tags:raise ValueError(f"Unit {key} requires unique non-empty tag keys")
            seen_tags.add(tag_key);tags.append(UnitTag(tag_key,label,engineering_unit,tuple(str(x) for x in tag_aliases),semantic))
        units.append(ProcessUnit(key,unit_name,tuple(tags),tuple(str(x) for x in aliases)))
    return SiteModel(name,tuple(units))

def load_site_model(config_path:str|Path|None=None)->SiteModel:
    configured=config_path or os.environ.get("FCC_SITE_CONFIG")
    if not configured:return default_site_model()
    path=Path(configured).expanduser();payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):raise ValueError("Site configuration root must be an object")
    return _site_from_payload(payload)

def site_runtime_status(config_path:str|Path|None=None)->dict[str,object]:
    configured=config_path or os.environ.get("FCC_SITE_CONFIG");site=load_site_model(config_path)
    return {"name":site.name,"source":"local-config" if configured else "development-catalog","configured":bool(configured),"units":[{"key":u.key,"name":u.name,"metrics":len(u.tags)} for u in site.units],"read_only":True}
