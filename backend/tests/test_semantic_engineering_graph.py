from backend.app.semantic_engineering_graph import build_semantic_engineering_graph, traverse_semantic_neighbors
from backend.app.site_model import default_site_model

def test_semantic_graph_links_tag_measurement_unit_and_hypothesis():
    graph=build_semantic_engineering_graph(
        unit_key="fcc",site=default_site_model(),
        hypotheses=[{"id":"h1","statement":"Investigate whether regenerator_dp relates to regenerator temperature"}],
        evidence_graph={"nodes":[{"id":"history:dp","kind":"evidence","label":"DP history","source_kind":"historian","provenance":{"tag_key":"regenerator_dp"}},{"id":"h1","kind":"hypothesis","label":"DP hypothesis"}],"edges":[{"from":"history:dp","to":"h1","relation":"supports"}]},
    )
    edges={(e["from"],e["to"],e["relation"]) for e in graph["edges"]}
    assert ("tag:regenerator_dp","measurement:regenerator_dp","measures") in edges
    assert ("measurement:regenerator_dp","unit:fcc","belongs_to_unit") in edges
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
