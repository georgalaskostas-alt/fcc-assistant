"""Read-only P&ID engineering graph: explicit evidence, never guessed connections.

This module is a foundation for future symbol/line detection. OCR labels alone
are insufficient evidence for process or instrument-signal connectivity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NodeKind = Literal["equipment", "instrument", "valve", "connector", "unknown"]
EdgeKind = Literal["process", "electrical_signal", "pneumatic_signal", "data_signal", "unknown"]
EvidenceKind = Literal["engineer_verified", "document_explicit"]


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: NodeKind
    tag: str
    page: int
    box: tuple[float, float, float, float]
    verified: bool = False


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    kind: EdgeKind
    evidence: EvidenceKind
    reference: str
    direction_verified: bool = False


@dataclass
class EngineeringGraph:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        if not node.id or node.page < 1 or not node.tag.strip():
            raise ValueError("Node requires an id, page and tag")
        if len(node.box) != 4 or any(not 0 <= value <= 1 for value in node.box):
            raise ValueError("Node coordinates must be normalized")
        x, y, w, h = node.box
        if x + w > 1 or y + h > 1:
            raise ValueError("Node box exceeds drawing bounds")
        if node.id in self.nodes:
            raise ValueError("Duplicate node id")
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError("Connection references unknown nodes")
        if edge.source == edge.target:
            raise ValueError("Self-connections require separate review")
        if not edge.reference.strip():
            raise ValueError("A connection requires an evidence reference")
        if edge.evidence == "engineer_verified" and not (
            self.nodes[edge.source].verified and self.nodes[edge.target].verified
        ):
            raise ValueError("Engineer-verified edges require verified endpoints")
        if edge in self.edges:
            raise ValueError("Duplicate connection")
        self.edges.append(edge)

    def neighbors(self, node_id: str, *, include_unverified: bool = False) -> list[dict]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        result = []
        for edge in self.edges:
            if edge.source != node_id and edge.target != node_id:
                continue
            if not include_unverified and edge.evidence != "engineer_verified":
                continue
            other = edge.target if edge.source == node_id else edge.source
            result.append({
                "node_id": other, "tag": self.nodes[other].tag,
                "kind": edge.kind, "evidence": edge.evidence,
                "reference": edge.reference,
                "direction": ("outgoing" if edge.source == node_id else "incoming")
                if edge.direction_verified else "unknown",
            })
        return result

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "read_only": True,
            "nodes": [
                {"id": n.id, "kind": n.kind, "tag": n.tag, "page": n.page,
                 "box": list(n.box), "verified": n.verified}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "kind": e.kind,
                 "evidence": e.evidence, "reference": e.reference,
                 "direction_verified": e.direction_verified}
                for e in self.edges
            ],
            "warning": "Graph edges require explicit evidence; OCR does not establish connectivity.",
        }


def graph_from_ocr(candidates: list[dict], page: int) -> EngineeringGraph:
    """Stage OCR hypotheses as unknown nodes, with NO edges or inferred equipment class."""
    graph = EngineeringGraph()
    for index, candidate in enumerate(candidates):
        box = candidate.get("box") or {}
        try:
            graph.add_node(GraphNode(
                id=f"p{page}-ocr-{index}", kind="unknown",
                tag=str(candidate["tag"]), page=page,
                box=tuple(float(box[key]) for key in ("x", "y", "width", "height")),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return graph
