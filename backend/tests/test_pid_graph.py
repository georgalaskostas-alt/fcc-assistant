from backend.app.pid_graph import EngineeringGraph, GraphNode, GraphEdge, graph_from_ocr
import pytest


def node(identifier, verified=False):
    return GraphNode(identifier, "instrument", identifier.upper(), 1, (0.1, 0.2, 0.1, 0.1), verified)


def test_ocr_creates_unverified_nodes_but_no_connections():
    graph = graph_from_ocr([{"tag": "PT101", "box": {"x": .1, "y": .2, "width": .1, "height": .1}}], 1)
    assert len(graph.nodes) == 1
    assert graph.edges == []
    assert graph.to_dict()["nodes"][0]["kind"] == "unknown"


def test_verified_signal_connection_preserves_direction_and_evidence():
    graph = EngineeringGraph()
    graph.add_node(node("pt101", True))
    graph.add_node(node("pic101", True))
    graph.add_edge(GraphEdge("pt101", "pic101", "electrical_signal", "engineer_verified", "loop-diagram-12", True))
    assert graph.neighbors("pic101")[0]["direction"] == "incoming"
    assert graph.neighbors("pt101")[0]["direction"] == "outgoing"


def test_unverified_endpoints_cannot_be_claimed_as_engineer_verified():
    graph = EngineeringGraph()
    graph.add_node(node("pt101"))
    graph.add_node(node("pic101", True))
    with pytest.raises(ValueError):
        graph.add_edge(GraphEdge("pt101", "pic101", "unknown", "engineer_verified", "drawing-1"))


def test_unknown_direction_remains_unknown():
    graph = EngineeringGraph()
    graph.add_node(node("a", True))
    graph.add_node(node("b", True))
    graph.add_edge(GraphEdge("a", "b", "process", "engineer_verified", "drawing-1"))
    assert graph.neighbors("a")[0]["direction"] == "unknown"


def test_document_evidence_is_not_silently_treated_as_engineer_verified():
    graph = EngineeringGraph()
    graph.add_node(node("a"))
    graph.add_node(node("b"))
    graph.add_edge(GraphEdge("a", "b", "data_signal", "document_explicit", "loop-sheet-1"))
    assert graph.neighbors("a") == []
    assert graph.neighbors("a", include_unverified=True)[0]["evidence"] == "document_explicit"


def test_invalid_coordinates_and_missing_reference_rejected():
    graph = EngineeringGraph()
    with pytest.raises(ValueError):
        graph.add_node(GraphNode("bad", "unknown", "BAD", 1, (.9, .9, .2, .2)))
    graph.add_node(node("a", True))
    graph.add_node(node("b", True))
    with pytest.raises(ValueError):
        graph.add_edge(GraphEdge("a", "b", "process", "engineer_verified", ""))
