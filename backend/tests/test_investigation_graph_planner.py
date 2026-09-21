from backend.app.investigation_graph_planner import semantic_discovery_candidates, semantic_candidates_to_actions, process_path_candidates, branch_process_path_candidates

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


def test_process_path_candidates_preserve_relationship_trace():
    graph={"nodes":[{"id":"equipment:fcc:reactor","kind":"equipment","equipment_key":"reactor","label":"Reactor"}]}
    paths={"paths":[{"nodes":["equipment:fcc:regenerator","equipment:fcc:reactor"],"relationships":["temperature_influence"]}]}
    candidates=process_path_candidates(process_paths=paths,graph=graph,synthesis={"resolved_tags":[]},limit=4)
    assert candidates[0]["equipment_key"]=="reactor"
    assert candidates[0]["path_relationships"]==["temperature_influence"]
    actions=semantic_candidates_to_actions(candidates=candidates,unit_key="fcc")
    assert actions[0]["tool"]=="search_archive"
    assert actions[0]["semantic_candidate"]["path_relationships"]==["temperature_influence"]


def test_process_path_planner_prunes_previous_no_gain_direction():
    graph={"nodes":[{"id":"equipment:fcc:reactor","kind":"equipment","equipment_key":"reactor","label":"Reactor"}]}
    paths={"paths":[{"nodes":["equipment:fcc:regenerator","equipment:fcc:reactor"],"relationships":["temperature_influence"]}]}
    synthesis={"resolved_tags":[],"process_path_information_gain":[{"candidate_key":"reactor","relationships":["temperature_influence"],"classification":"no_information_gain","score":0}]}
    assert process_path_candidates(process_paths=paths,graph=graph,synthesis=synthesis,limit=4)==[]

def test_process_path_planner_rewards_previously_useful_direction():
    graph={"nodes":[{"id":"equipment:fcc:reactor","kind":"equipment","equipment_key":"reactor","label":"Reactor"}]}
    paths={"paths":[{"nodes":["equipment:fcc:regenerator","equipment:fcc:reactor"],"relationships":["temperature_influence"]}]}
    synthesis={"resolved_tags":[],"process_path_information_gain":[{"candidate_key":"reactor","relationships":["temperature_influence"],"classification":"useful_path","score":5}]}
    candidates=process_path_candidates(process_paths=paths,graph=graph,synthesis=synthesis,limit=4)
    assert candidates[0]["prior_path_attempts"]==1
    assert candidates[0]["adaptive_value"]>6


def test_branch_process_paths_keep_hypothesis_ownership_and_feedback_isolation():
    graph={"nodes":[
        {"id":"h1","kind":"hypothesis","label":"H1"},
        {"id":"h2","kind":"hypothesis","label":"H2"},
        {"id":"equipment:fcc:regenerator","kind":"equipment","equipment_key":"regenerator","label":"Regenerator"},
        {"id":"equipment:fcc:reactor","kind":"equipment","equipment_key":"reactor","label":"Reactor"},
    ],"edges":[
        {"from":"equipment:fcc:regenerator","to":"h1","relation":"investigated_in"},
        {"from":"equipment:fcc:regenerator","to":"h2","relation":"investigated_in"},
        {"from":"equipment:fcc:regenerator","to":"equipment:fcc:reactor","relation":"temperature_influence"},
    ]}
    def trace_fn(**kwargs):
        return {"paths":[{"nodes":["equipment:fcc:regenerator","equipment:fcc:reactor"],"relationships":["temperature_influence"]}]}
    synthesis={"process_path_information_gain":[
        {"hypothesis_branch_id":"h1","candidate_key":"reactor","relationships":["temperature_influence"],"classification":"no_information_gain","score":0},
        {"hypothesis_branch_id":"h2","candidate_key":"reactor","relationships":["temperature_influence"],"classification":"useful_path","score":5},
    ]}
    candidates=branch_process_path_candidates(hypotheses=[{"id":"h1","statement":"A"},{"id":"h2","statement":"B"}],graph=graph,synthesis=synthesis,trace_fn=trace_fn,limit_per_branch=2)
    assert [item["hypothesis_branch_id"] for item in candidates]==["h2"]
    actions=semantic_candidates_to_actions(candidates=candidates,unit_key="fcc")
    assert actions[0]["hypothesis_branch_id"]=="h2"
