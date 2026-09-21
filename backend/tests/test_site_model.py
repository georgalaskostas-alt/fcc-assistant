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


def test_load_site_model_supports_configured_engineering_topology(tmp_path):
    path=tmp_path/"site-topology.json"
    path.write_text(json.dumps({"name":"Demo Refinery","units":[{
        "key":"fcc","name":"FCC",
        "sections":[{"key":"rr","name":"Reaction & Regeneration"}],
        "equipment":[{"key":"rx","name":"Reactor","section_key":"rr","type":"reactor"},{"key":"rg","name":"Regenerator","section_key":"rr","type":"regenerator"}],
        "streams":[{"key":"cat","name":"Catalyst circulation","from_equipment":"rg","to_equipment":"rx"}],
        "tags":[{"key":"rg_dp","label":"Regenerator DP","unit":"bar","semantic_key":"regenerator_dp","equipment_key":"rg"},{"key":"cat_rate","label":"Catalyst Rate","unit":"t/h","semantic_key":"catalyst_rate","equipment_key":"rx","stream_key":"cat"}]
    }]}),encoding="utf-8")
    site=load_site_model(path);unit=site.find_unit("fcc")
    assert unit is not None
    assert unit.sections[0].key=="rr"
    assert unit.equipment[1].section_key=="rr"
    assert unit.streams[0].from_equipment=="rg"
    assert unit.tags[0].equipment_key=="rg"
    assert unit.tags[1].stream_key=="cat"
