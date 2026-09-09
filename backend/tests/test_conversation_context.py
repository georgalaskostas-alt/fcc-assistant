from app.conversation_context import build_conversation_context


def test_context_keeps_only_recent_six_turns():
    state={"recent_turns":[{"user":f"u{i}","assistant":f"a{i}","action":"answer","unit":"fcc"} for i in range(9)]}
    context=build_conversation_context(state)
    assert [turn["user"] for turn in context["recent_turns"]]==["u3","u4","u5","u6","u7","u8"]


def test_context_exposes_reference_memory_without_full_widgets():
    state={
        "last_requested_unit_key":"hcu",
        "last_unit_key":"fcc",
        "last_widget":{"id":"w1","type":"trend","title":"Feed","unit_key":"fcc","tag_keys":["fcc_feed"],"period":"8h","layout":{"width":12},"secret":"drop"},
        "last_action_context":{"last_action":"add_widget","last_touched_widget_ids":["w1"]},
        "last_removed_widgets":[{"id":"old1","title":"Old"}],
        "pending_intent":{"action":"add","missing":["metrics"]},
    }
    context=build_conversation_context(state)
    assert context["last_requested_unit_key"]=="hcu"
    assert context["last_widget"]["id"]=="w1"
    assert "layout" not in context["last_widget"]
    assert "secret" not in context["last_widget"]
    assert context["last_removed_widget_ids"]==["old1"]
    assert context["pending_intent"]["action"]=="add"


def test_context_truncates_long_dialogue_text():
    context=build_conversation_context({"recent_turns":[{"user":"x"*900,"assistant":"y"*900}]})
    assert len(context["recent_turns"][0]["user"])==500
    assert len(context["recent_turns"][0]["assistant"])==500
