from backend.app.pid_topology import propose_topology


def segment(x1, y1, x2, y2, orientation="horizontal", region="drawing_area_candidate"):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "orientation": orientation, "region_hint": region}


def test_nearby_endpoints_are_only_review_proposals():
    result = propose_topology([
        segment(.1, .2, .3, .2),
        segment(.302, .2, .5, .2),
    ])
    assert result["count"] == 1
    assert result["verified_connections"] == 0
    assert result["proposals"][0]["status"] == "requires_engineer_review"


def test_crossing_without_endpoint_match_is_not_connected():
    result = propose_topology([
        segment(.1, .5, .9, .5),
        segment(.5, .1, .5, .9, "vertical"),
    ])
    assert result["count"] == 0


def test_title_block_candidates_are_ignored():
    result = propose_topology([
        segment(.1, .2, .3, .2),
        segment(.3, .2, .5, .2, region="title_block_candidate"),
    ])
    assert result["count"] == 0
