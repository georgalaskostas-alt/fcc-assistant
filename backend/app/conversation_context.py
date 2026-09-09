from __future__ import annotations

from typing import Any

_MAX_TURNS = 6
_MAX_TEXT = 500


def _text(value: object) -> str:
    return str(value or "").strip()[:_MAX_TEXT]


def _turn(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "user": _text(value.get("user")),
        "assistant": _text(value.get("assistant")),
        "action": _text(value.get("action")),
        "unit": _text(value.get("unit")),
    }


def build_conversation_context(state: dict[str, object]) -> dict[str, Any]:
    """Return a small, explicit dialogue snapshot for the local planner.

    The planner should see enough history to resolve phrases such as "αυτό",
    "και στο HCU" or "κάν' τα 8 ώρες", without receiving an ever-growing
    state blob. Current-turn safety validation remains authoritative.
    """
    raw_turns = state.get("recent_turns")
    turns = []
    if isinstance(raw_turns, list):
        for raw in raw_turns[-_MAX_TURNS:]:
            item = _turn(raw)
            if item is not None:
                turns.append(item)

    last_widget = state.get("last_widget")
    widget = dict(last_widget) if isinstance(last_widget, dict) else None
    if widget is not None:
        widget = {
            key: widget.get(key)
            for key in ("id", "type", "title", "unit_key", "tag_keys", "period")
            if key in widget
        }

    action_context = state.get("last_action_context")
    action = dict(action_context) if isinstance(action_context, dict) else {}

    removed = state.get("last_removed_widgets")
    removed_ids = [str(w.get("id")) for w in removed if isinstance(w, dict) and w.get("id")] if isinstance(removed, list) else []

    return {
        "recent_turns": turns,
        "last_requested_unit_key": state.get("last_requested_unit_key"),
        "last_unit_key": state.get("last_unit_key"),
        "last_widget": widget,
        "last_action_context": {
            "last_action": action.get("last_action"),
            "last_touched_widget_ids": list(action.get("last_touched_widget_ids") or [])[:20],
        },
        "last_removed_widget_ids": removed_ids[:20],
        "pending_intent": state.get("pending_intent"),
    }
