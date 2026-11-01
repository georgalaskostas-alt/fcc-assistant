"""Conservative topology hypotheses from raster line segments.

Crossings are NOT assumed to be connected. Nearby endpoints produce review
candidates only; no process, signal, or flow direction is inferred.
"""
from __future__ import annotations

from math import hypot


def propose_topology(segments: list[dict], *, tolerance: float = 0.006,
                     max_proposals: int = 1000) -> dict:
    if not 0 < tolerance <= 0.05:
        raise ValueError("Invalid normalized tolerance")
    usable = [
        (index, item) for index, item in enumerate(segments)
        if item.get("region_hint") != "title_block_candidate"
        and item.get("orientation") in ("horizontal", "vertical")
    ]
    proposals: list[dict] = []
    for pos, (left_id, left) in enumerate(usable):
        a = ((left["x1"], left["y1"]), (left["x2"], left["y2"]))
        for right_id, right in usable[pos + 1:]:
            b = ((right["x1"], right["y1"]), (right["x2"], right["y2"]))
            matches = [(i, j, hypot(p[0]-q[0], p[1]-q[1]))
                       for i, p in enumerate(a) for j, q in enumerate(b)]
            i, j, distance = min(matches, key=lambda entry: entry[2])
            if distance <= tolerance:
                proposals.append({
                    "segment_a": left_id, "segment_b": right_id,
                    "endpoint_a": i, "endpoint_b": j,
                    "distance": round(distance, 6),
                    "kind": "nearby_endpoints",
                    "status": "requires_engineer_review",
                })
                if len(proposals) >= max_proposals:
                    return {"proposals": proposals, "count": len(proposals),
                            "truncated": True, "verified_connections": 0,
                            "warning": "Endpoint proximity is not proof of connectivity."}
    return {"proposals": proposals, "count": len(proposals),
            "truncated": False, "verified_connections": 0,
            "warning": "Endpoint proximity is not proof of connectivity. Crossings remain unresolved."}
