from backend.app.semantic_engineering_graph import build_semantic_engineering_graph
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
