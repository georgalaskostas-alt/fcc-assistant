from backend.app.investigation_graph_planner import semantic_discovery_candidates, semantic_candidates_to_actions

def test_semantic_candidates_create_only_governed_read_actions():
    neighborhood={"nodes":[
        {"id":"tag:regenerator_o2","kind":"tag","tag_key":"regenerator_o2","label":"Regenerator O2"},
        {"id":"equipment:fcc:regenerator","kind":"equipment","equipment_key":"regenerator","label":"Regenerator"},
    ]}
    candidates=semantic_discovery_candidates(neighborhood=neighborhood,synthesis={"resolved_tags":[],"discovered_tags":{"items":[]}},limit=4)
    actions=semantic_candidates_to_actions(candidates=candidates,unit_key="fcc")
    assert {a["tool"] for a in actions}=={"search_tags","search_archive"}
    assert all(a["tool"] not in {"set_value","write_tag","approve_document"} for a in actions)
    archive=next(a for a in actions if a["tool"]=="search_archive")
    assert archive["arguments"]["equipment_key"]=="regenerator"
    assert archive["arguments"]["approved_only"] is True

def test_semantic_measurement_candidate_excludes_already_known_tags():
    neighborhood={"nodes":[{"kind":"tag","tag_key":"regenerator_o2","label":"Regenerator O2"}]}
    candidates=semantic_discovery_candidates(neighborhood=neighborhood,synthesis={"resolved_tags":["regenerator_o2"],"discovered_tags":{"items":[]}})
    assert candidates==[]
