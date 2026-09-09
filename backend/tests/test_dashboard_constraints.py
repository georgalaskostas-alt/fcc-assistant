from app.dashboard_constraints import conflicts_with_current_turn, explicit_action, plan_action_family, target_unit_keys


def _widgets():
    return [
        {"id":"fcc-feed","type":"trend","unit_key":"fcc","title":"FCC Feed"},
        {"id":"hcu-feed","type":"trend","unit_key":"hcu","title":"HCU Feed"},
    ]


def test_explicit_add_rejects_update_plan():
    plan={"action":"update_widgets","target_ids":["fcc-feed"],"period":"8h"}
    conflicts=conflicts_with_current_turn("Βάλε ένα διάγραμμα feed στο FCC για 8 ώρες",plan,{"fcc"},_widgets())
    assert any("explicit action add" in item for item in conflicts)


def test_explicit_remove_accepts_remove_plan():
    plan={"action":"remove_widgets","target_ids":["fcc-feed"]}
    assert conflicts_with_current_turn("Αφαίρεσε το feed από το FCC",plan,{"fcc"},_widgets())==[]


def test_restore_is_compatible_with_add_widgets_snapshot():
    plan={"action":"add_widgets","widgets":[{"id":"fcc-feed","unit_key":"fcc"}]}
    assert explicit_action("Επανέφερε το διάγραμμα στο FCC")=="restore"
    assert conflicts_with_current_turn("Επανέφερε το διάγραμμα στο FCC",plan,{"fcc"},_widgets())==[]


def test_explicit_unit_rejects_plan_targeting_other_unit():
    plan={"action":"remove_widgets","target_ids":["hcu-feed"]}
    conflicts=conflicts_with_current_turn("Αφαίρεσε το feed από το FCC",plan,{"fcc"},_widgets())
    assert any("explicit units" in item for item in conflicts)


def test_transaction_collects_action_families_and_units():
    plan={
        "action":"transaction",
        "steps":[
            {"action":"remove_widget","target_id":"fcc-feed"},
            {"action":"add_widget","widget":{"id":"hcu-new","unit_key":"hcu"}},
        ],
    }
    assert plan_action_family(plan)=={"remove","add"}
    assert target_unit_keys(plan,_widgets())=={"fcc","hcu"}
