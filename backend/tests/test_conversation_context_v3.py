from app.conversation_context import build_conversation_context


def test_context_is_bounded_and_ignores_empty_turns():
    state = {"recent_turns": [{"user": f"turn-{i}", "assistant": "ok", "action": "add", "unit": "fcc"} for i in range(10)] + [{}], "last_action_context": {"last_touched_widget_ids": [f"w{i}" for i in range(40)]}}
    context = build_conversation_context(state)
    assert len(context["recent_turns"]) <= 6
    assert context["recent_turns"][-1]["user"] == "turn-9"
    assert len(context["last_action_context"]["last_touched_widget_ids"]) == 20


def test_pending_intent_only_exposes_known_planner_fields():
    state = {"pending_intent": {"action": "add", "units": ["fcc"], "metrics": ["feed"], "missing": ["period"], "arbitrary_nested_payload": {"should": "not leak"}}}
    assert build_conversation_context(state)["pending_intent"] == {"action": "add", "units": ["fcc"], "metrics": ["feed"], "missing": ["period"]}


def test_last_widget_tag_keys_are_bounded_strings():
    widget = build_conversation_context({"last_widget": {"id": "x", "tag_keys": list(range(50)), "unknown": "drop"}})["last_widget"]
    assert widget["id"] == "x"
    assert widget["tag_keys"] == [str(i) for i in range(20)]
    assert "unknown" not in widget


def test_text_fields_are_bounded():
    huge = "x" * 2000
    context = build_conversation_context({"recent_turns": [{"user": huge}], "last_requested_unit_key": huge})
    assert len(context["recent_turns"][0]["user"]) == 500
    assert len(context["last_requested_unit_key"]) == 500


def test_nested_objects_are_not_stringified_into_planner_context():
    context = build_conversation_context({"recent_turns": [{"user": {"unexpected": "object"}, "assistant": "ok"}], "last_requested_unit_key": {"bad": "fcc"}, "last_action_context": {"last_touched_widget_ids": [{"bad": "id"}, "good-id"]}})
    assert context["recent_turns"][0]["user"] == ""
    assert context["last_requested_unit_key"] is None
    assert context["last_action_context"]["last_touched_widget_ids"] == ["good-id"]


def test_pending_nested_values_are_dropped_not_stringified():
    pending = build_conversation_context({"pending_intent": {"action": {"bad": "add"}, "units": [{"bad": "fcc"}, "hcu"], "metrics": ["feed"]}})["pending_intent"]
    assert pending["action"] == ""
    assert pending["units"] == ["hcu"]
    assert pending["metrics"] == ["feed"]


def test_removed_widget_ids_are_bounded_and_sanitized():
    removed = [{"id": f"w{i}"} for i in range(30)] + [{"id": {"bad": "id"}}]
    assert build_conversation_context({"last_removed_widgets": removed})["last_removed_widget_ids"] == [f"w{i}" for i in range(20)]


def test_scalar_widget_fields_are_sanitized():
    widget = build_conversation_context({"last_widget": {"id": {"bad": "id"}, "title": "Feed", "unit_key": "fcc", "period": ["bad"]}})["last_widget"]
    assert widget["id"] == ""
    assert widget["title"] == "Feed"
    assert widget["unit_key"] == "fcc"
    assert widget["period"] == ""


def test_non_list_recent_turns_are_ignored():
    assert build_conversation_context({"recent_turns": {"bad": "shape"}})["recent_turns"] == []


def test_non_dict_pending_intent_is_ignored():
    assert build_conversation_context({"pending_intent": ["bad"]})["pending_intent"] is None


def test_none_and_empty_state_are_safe():
    context = build_conversation_context({})
    assert context["recent_turns"] == []
    assert context["last_widget"] is None
    assert context["pending_intent"] is None
    assert context["last_requested_unit_key"] is None


def test_recent_turn_keeps_only_expected_fields():
    turn = build_conversation_context({"recent_turns": [{"user": "x", "assistant": "y", "action": "add", "unit": "fcc", "secret": "drop"}]})["recent_turns"][0]
    assert turn == {"user": "x", "assistant": "y", "action": "add", "unit": "fcc"}


def test_pending_lists_are_bounded():
    pending = build_conversation_context({"pending_intent": {"action": "add", "units": [f"u{i}" for i in range(50)], "metrics": [f"m{i}" for i in range(50)], "missing": [f"x{i}" for i in range(50)]}})["pending_intent"]
    assert len(pending["units"]) == 20
    assert len(pending["metrics"]) == 20
    assert len(pending["missing"]) == 20


def test_action_context_scalar_is_sanitized():
    context = build_conversation_context({"last_action_context": {"last_action": {"bad": "remove"}, "last_touched_widget_ids": ["x"]}})
    assert context["last_action_context"] == {"last_action": None, "last_touched_widget_ids": ["x"]}


def test_recent_turn_preserves_greek_operator_text():
    context = build_conversation_context({"recent_turns": [{"user": "Αφαίρεσε αυτό", "assistant": "Έγινε", "action": "remove", "unit": "fcc"}]})
    assert context["recent_turns"][0]["user"] == "Αφαίρεσε αυτό"
    assert context["recent_turns"][0]["assistant"] == "Έγινε"


def test_boolean_and_numeric_scalars_are_safe_text():
    context = build_conversation_context({"recent_turns": [{"user": 123, "assistant": True}]})
    assert context["recent_turns"][0]["user"] == "123"
    assert context["recent_turns"][0]["assistant"] == "True"


def test_pending_scalar_fields_are_text_bounded():
    huge = "p" * 1000
    pending = build_conversation_context({"pending_intent": {"action": huge, "period": huge, "reference": huge}})["pending_intent"]
    assert len(pending["action"]) == 500
    assert len(pending["period"]) == 500
    assert len(pending["reference"]) == 500
