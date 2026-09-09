from __future__ import annotations

import re


def explicit_action(command: str) -> str | None:
    text = command.casefold()
    if re.search(r"\b(add|create|show|put)\b", text) or any(x in text for x in ("βάλε", "βαλε", "πρόσθε", "προσθε", "δημιούργ", "δημιουργ")):
        return "add"
    if re.search(r"\b(remove|delete|hide)\b", text) or any(x in text for x in ("αφαίρε", "αφαιρε", "σβή", "σβη", "διέγρα", "διεγρα")):
        return "remove"
    if re.search(r"\b(restore|bring back)\b", text) or any(x in text for x in ("ξαναβάλε", "ξαναβαλε", "επαναφέρ", "επαναφερ", "βάλε πίσω", "βαλε πισω")):
        return "restore"
    if re.search(r"\b(replace|swap)\b", text) or "αντικατάστ" in text or "αντικαταστ" in text:
        return "replace"
    return None


def _steps(plan: dict[str, object]) -> list[dict[str, object]]:
    raw = plan.get("steps")
    if str(plan.get("action", "")) == "transaction" and isinstance(raw, list):
        return [dict(x) for x in raw if isinstance(x, dict)]
    return [plan]


def plan_action_family(plan: dict[str, object]) -> set[str]:
    families: set[str] = set()
    for step in _steps(plan):
        action = str(step.get("action", "")).casefold()
        if action in {"add_widget", "add_widgets"}:
            families.add("add")
        elif action in {"remove_widget", "remove_widgets"}:
            families.add("remove")
        elif action == "replace_widget":
            families.add("replace")
        elif action == "update_widgets":
            families.add("update")
    return families


def target_unit_keys(plan: dict[str, object], widgets: list[dict[str, object]]) -> set[str]:
    by_id = {str(w.get("id")): str(w.get("unit_key", "")).casefold() for w in widgets if w.get("id")}
    units: set[str] = set()
    for step in _steps(plan):
        widget = step.get("widget")
        if isinstance(widget, dict) and widget.get("unit_key"):
            units.add(str(widget["unit_key"]).casefold())
        raw_widgets = step.get("widgets")
        if isinstance(raw_widgets, list):
            units.update(
                str(w.get("unit_key", "")).casefold()
                for w in raw_widgets
                if isinstance(w, dict) and w.get("unit_key")
            )
        target_id = step.get("target_id")
        if target_id is not None and str(target_id) in by_id:
            units.add(by_id[str(target_id)])
        target_ids = step.get("target_ids")
        if isinstance(target_ids, list):
            units.update(by_id[str(x)] for x in target_ids if str(x) in by_id)
    return {x for x in units if x}


def conflicts_with_current_turn(
    command: str,
    plan: dict[str, object],
    explicit_units: set[str],
    widgets: list[dict[str, object]],
) -> list[str]:
    conflicts: list[str] = []
    action = explicit_action(command)
    families = plan_action_family(plan)

    # Restoring an exact snapshot is executed as add_widget(s), so an explicit
    # restore command is compatible with an ADD-family execution plan.
    action_is_compatible = action in families or (action == "restore" and "add" in families)
    if action and families and not action_is_compatible:
        conflicts.append(f"explicit action {action} conflicts with plan actions {sorted(families)}")

    targets = target_unit_keys(plan, widgets)
    if explicit_units and targets and not targets.issubset(explicit_units):
        conflicts.append(f"explicit units {sorted(explicit_units)} conflict with target units {sorted(targets)}")
    return conflicts
