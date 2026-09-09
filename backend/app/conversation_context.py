from __future__ import annotations

from typing import Any

_MAX_TURNS = 6
_MAX_TEXT = 500
_MAX_IDS = 20


def _text(value: object) -> str:
    if value is None or not isinstance(value, (str, int, float, bool)):
        return ""
    return str(value).strip()[:_MAX_TEXT]


def _turn(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    item = {"user": _text(value.get("user")), "assistant": _text(value.get("assistant")), "action": _text(value.get("action")), "unit": _text(value.get("unit"))}
    return item if any(item.values()) else None


def _strings(value: object, limit: int = _MAX_IDS) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value:
        text = _text(raw)
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def build_conversation_context(state: dict[str, object]) -> dict[str, Any]:
    """Build bounded supporting context. The current user turn stays authoritative."""
    raw_turns = state.get("recent_turns")
    turns: list[dict[str, object]] = []
    if isinstance(raw_turns, list):
        for raw in raw_turns[-_MAX_TURNS:]:
            item = _turn(raw)
            if item is not None:
                turns.append(item)

    last_widget = state.get("last_widget")
    widget = dict(last_widget) if isinstance(last_widget, dict) else None
    if widget is not None:
        widget = {key: widget.get(key) for key in ("id", "type", "title", "unit_key", "tag_keys", "period") if key in widget}
        for key in ("id", "type", "title", "unit_key", "period"):
            if key in widget:
                widget[key] = _text(widget[key])
        if "tag_keys" in widget:
            widget["tag_keys"] = _strings(widget["tag_keys"])

    action_context = state.get("last_action_context")
    action = dict(action_context) if isinstance(action_context, dict) else {}

    removed = state.get("last_removed_widgets")
    removed_ids = [_text(w.get("id")) for w in removed if isinstance(w, dict) and _text(w.get("id"))] if isinstance(removed, list) else []

    pending = state.get("pending_intent")
    safe_pending: dict[str, object] | None = None
    if isinstance(pending, dict):
        safe_pending = {key: pending.get(key) for key in ("action", "units", "metrics", "scope", "reference", "widget_type", "period", "missing") if key in pending}
        for key in ("units", "metrics", "missing"):
            if key in safe_pending:
                safe_pending[key] = _strings(safe_pending[key])
        for key in ("action", "scope", "reference", "widget_type", "period"):
            if key in safe_pending:
                safe_pending[key] = _text(safe_pending[key])

    return {
        "recent_turns": turns,
        "last_requested_unit_key": _text(state.get("last_requested_unit_key")) or None,
        "last_unit_key": _text(state.get("last_unit_key")) or None,
        "last_widget": widget,
        "last_action_context": {"last_action": _text(action.get("last_action")) or None, "last_touched_widget_ids": _strings(action.get("last_touched_widget_ids"))},
        "last_removed_widget_ids": removed_ids[:_MAX_IDS],
        "pending_intent": safe_pending,
    }
