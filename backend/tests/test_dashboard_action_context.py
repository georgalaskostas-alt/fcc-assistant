from pathlib import Path

from app.dashboard_dialogue import DashboardDialogueStore


def _widget(widget_id: str, unit: str, tag: str, period: str = "16h") -> dict[str, object]:
    return {
        "id": widget_id,
        "type": "trend",
        "title": "Feed Flow",
        "unit_key": unit,
        "tag_keys": [tag],
        "period": period,
        "layout": {"order": 0, "width": 12, "height": "tall"},
    }


def test_transaction_persists_touched_widget_ids(tmp_path: Path):
    dialogue = DashboardDialogueStore(tmp_path / "dialogue.json")
    fcc = _widget("fcc-feed-1", "fcc", "feed_flow")
    hcu = _widget("hcu-feed-1", "hcu", "hcu_feed_flow")
    plan = {
        "action": "transaction",
        "steps": [
            {"action": "add_widget", "widget": fcc, "read_only": True, "requires_confirmation": False},
            {"action": "add_widget", "widget": hcu, "read_only": True, "requires_confirmation": False},
        ],
        "read_only": True,
        "requires_confirmation": False,
    }

    dialogue.remember(
        "default",
        "Βάλε feed flow στο FCC και HCU",
        plan,
        {"widgets": [fcc, hcu]},
        "Έγινε.",
        previous_widgets=[],
    )

    context = dialogue.get_action_context("default")
    assert context["last_action"] == "transaction"
    assert context["last_touched_widget_ids"] == ["fcc-feed-1", "hcu-feed-1"]


def test_clarify_does_not_erase_previous_action_context(tmp_path: Path):
    dialogue = DashboardDialogueStore(tmp_path / "dialogue.json")
    widget = _widget("fcc-feed-1", "fcc", "feed_flow")
    add_plan = {"action": "add_widget", "widget": widget, "read_only": True, "requires_confirmation": False}
    dialogue.remember("default", "Βάλε feed flow στο FCC", add_plan, {"widgets": [widget]}, "Έγινε.", previous_widgets=[])

    clarify_plan = {"action": "clarify", "read_only": True, "requires_confirmation": False, "needs_clarification": True}
    dialogue.remember("default", "Κάνε το ίδιο", clarify_plan, {"widgets": [widget]}, "Ποιο εννοείς;", previous_widgets=[widget])

    context = dialogue.get_action_context("default")
    assert context["last_action"] == "add_widget"
    assert context["last_touched_widget_ids"] == ["fcc-feed-1"]


def test_update_widgets_records_exact_batch(tmp_path: Path):
    dialogue = DashboardDialogueStore(tmp_path / "dialogue.json")
    fcc = _widget("fcc-feed-1", "fcc", "feed_flow", "8h")
    hcu = _widget("hcu-feed-1", "hcu", "hcu_feed_flow", "8h")
    before = [fcc, hcu]
    after = [{**fcc, "period": "16h"}, {**hcu, "period": "16h"}]
    plan = {
        "action": "update_widgets",
        "target_ids": ["fcc-feed-1", "hcu-feed-1"],
        "period": "16h",
        "read_only": True,
        "requires_confirmation": False,
    }

    dialogue.remember("default", "Κάντα 16 ώρες", plan, {"widgets": after}, "Έγινε.", previous_widgets=before)

    context = dialogue.get_action_context("default")
    assert context["last_action"] == "update_widgets"
    assert context["last_touched_widget_ids"] == ["fcc-feed-1", "hcu-feed-1"]
