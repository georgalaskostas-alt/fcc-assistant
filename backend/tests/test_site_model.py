import json

from app.site_model import load_site_model


def test_load_site_model_supports_multiple_units(tmp_path):
    path = tmp_path / "site.json"
    path.write_text(json.dumps({
        "name": "Demo Refinery",
        "units": [
            {
                "key": "fcc",
                "name": "FCC",
                "tags": [{"key": "feed", "label": "Feed", "unit": "m3/h", "aliases": ["τροφοδοσία"]}],
            },
            {
                "key": "cdu",
                "name": "CDU",
                "tags": [{"key": "feed", "label": "Crude Feed", "unit": "m3/h", "aliases": ["crude"]}],
            },
        ],
    }), encoding="utf-8")

    site = load_site_model(path)
    assert site.name == "Demo Refinery"
    assert [unit.key for unit in site.units] == ["fcc", "cdu"]
    assert site.resolve_tag("cdu", "crude").label == "Crude Feed"
