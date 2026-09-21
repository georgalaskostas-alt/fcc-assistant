from backend.app.semantic_engineering_graph import build_semantic_engineering_graph, traverse_semantic_neighbors, trace_process_paths
from backend.app.site_model import default_site_model, SiteModel, ProcessUnit, ProcessSection, Equipment, ProcessStream, UnitTag, EngineeringRelationship

def test_semantic_graph_links_tag_measurement_unit_and_hypothesis():
    graph=build_semantic_engineering_graph(
        unit_key="fcc",site=default_site_model(),
        hypotheses=[{"id":"h1","statement":"Investigate whether regenerator_dp relates to regenerator temperature"}],
        evidence_graph={"nodes":[{"id":"history:dp","kind":"evidence","label":"DP history","source_kind":"historian","provenance":{"tag_key":"regenerator_dp"}},{"id":"h1","kind":"hypothesis","label":"DP hypothesis"}],"edges":[{"from":"history:dp","to":"h1","relation":"supports"}]},
    )
    edges={(e["from"],e["to"],e["relation"]) for e in graph["edges"]}
    assert ("tag:regenerator_dp","measurement:regenerator_dp","measures") in edges
    assert ("measurement:regenerator_dp","equipment:fcc:regenerator","measurement_of") in edges
    assert ("equipment:fcc:regenerator","section:fcc:reaction_regeneration","belongs_to_section") in edges
    assert ("section:fcc:reaction_regeneration","unit:fcc","belongs_to_unit") in edges
    assert ("history:dp","tag:regenerator_dp","derived_from") in edges
    assert ("measurement:regenerator_dp","h1","investigated_in") in edges
    assert graph["read_only"] is True
    assert graph["causal_inference"] is False


def test_semantic_hierarchy_and_bounded_traversal_reach_equipment_section_unit():
    graph=build_semantic_engineering_graph(
        unit_key="fcc",site=default_site_model(),
        hypotheses=[{"id":"h1","statement":"Investigate regenerator_dp"}],
        evidence_graph={"nodes":[{"id":"h1","kind":"hypothesis","label":"DP hypothesis"}],"edges":[]},
    )
    edges={(e["from"],e["to"],e["relation"]) for e in graph["edges"]}
    assert ("measurement:regenerator_dp","equipment:fcc:regenerator","measurement_of") in edges
    assert ("equipment:fcc:regenerator","section:fcc:reaction_regeneration","belongs_to_section") in edges
    assert ("section:fcc:reaction_regeneration","unit:fcc","belongs_to_unit") in edges
    assert ("unit:fcc","refinery:site","belongs_to_refinery") in edges
    neighborhood=traverse_semantic_neighbors(graph=graph,start_ids=["h1"],max_depth=3,max_nodes=12)
    ids={n["id"] for n in neighborhood["nodes"]}
    assert "measurement:regenerator_dp" in ids
    assert "equipment:fcc:regenerator" in ids
    assert neighborhood["bounded"] is True
    assert neighborhood["causal_inference"] is False


def test_semantic_graph_uses_configured_equipment_sections_and_streams():
    site=SiteModel("Configured Refinery",(ProcessUnit(
        "fcc","FCC",
        (UnitTag("cat_rate","Catalyst Rate","t/h",(),"catalyst_rate","reactor","cat_circ"),),
        (),(ProcessSection("rr","Reaction & Regeneration"),),
        (Equipment("regenerator","Regenerator","rr","regenerator"),Equipment("reactor","Reactor","rr","reactor")),
        (ProcessStream("cat_circ","Catalyst Circulation","regenerator","reactor"),),
    ),))
    graph=build_semantic_engineering_graph(unit_key="fcc",site=site,hypotheses=[],evidence_graph={"nodes":[],"edges":[]})
    edges={(e["from"],e["to"],e["relation"]) for e in graph["edges"]}
    assert ("equipment:fcc:regenerator","stream:fcc:cat_circ","feeds_stream") in edges
    assert ("stream:fcc:cat_circ","equipment:fcc:reactor","feeds_equipment") in edges
    assert ("measurement:catalyst_rate","equipment:fcc:reactor","measurement_of") in edges
    assert ("measurement:catalyst_rate","stream:fcc:cat_circ","measurement_of_stream") in edges
    assert ("equipment:fcc:reactor","section:fcc:rr","belongs_to_section") in edges


def test_configured_engineering_relationship_supports_directed_process_path():
    site=SiteModel("Refinery",(ProcessUnit("fcc","FCC",(),(),(),(
        Equipment("reactor","Reactor","rr"),Equipment("regenerator","Regenerator","rr"),
    ),(),(
        EngineeringRelationship("equipment","regenerator","equipment","reactor","temperature_influence","engineering_context",False),
    )),))
    graph=build_semantic_engineering_graph(unit_key="fcc",site=site,hypotheses=[],evidence_graph={"nodes":[],"edges":[]})
    assert any(e["relation"]=="temperature_influence" for e in graph["edges"])
    traced=trace_process_paths(graph=graph,start_ids=["equipment:fcc:regenerator"],max_depth=3)
    assert any(p["nodes"][-1]=="equipment:fcc:reactor" and "temperature_influence" in p["relationships"] for p in traced["paths"])
    assert traced["causal_inference"] is False
