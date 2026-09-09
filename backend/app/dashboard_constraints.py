from __future__ import annotations

import re


def explicit_action_families(command: str) -> set[str]:
    text = command.casefold()
    families: set[str] = set()

    restore = (
        bool(re.search(r"\b(restore|bring back)\b", text))
        or any(x in text for x in ("ξαναβάλε", "ξαναβαλε", "επαναφέρ", "επαναφερ", "επανέφερ", "επανεφερ"))
        or bool(re.search(r"\b(βάλε|βαλε)\b.*\b(πίσω|πισω)\b", text))
    )
    if restore:
        families.add("restore")

    add = bool(re.search(r"\b(add|create|show|put)\b", text)) or any(
        x in text for x in ("βάλε", "βαλε", "πρόσθε", "προσθε", "δημιούργ", "δημιουργ")
    )
    # Restore phrases often contain "βάλε". Do not count that embedded verb as
    # a second ADD request unless the turn also contains a separate add signal.
    if add and not restore:
        families.add("add")

    if re.search(r"\b(remove|delete|hide)\b", text) or any(
        x in text for x in ("αφαίρε", "αφαιρε", "βγάλε", "βγαλε", "σβή", "σβη", "διέγρα", "διεγρα")
    ):
        families.add("remove")
    if re.search(r"\b(replace|swap)\b", text) or "αντικατάστ" in text or "αντικαταστ" in text:
        families.add("replace")
    return families


def explicit_action(command: str) -> str | None:
    families = explicit_action_families(command)
    # Preserve the legacy single-action API for callers that only need a guard.
    for action in ("restore", "add", "remove", "replace"):
        if action in families:
            return action
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
            units.update(str(w.get("unit_key", "")).casefold() for w in raw_widgets if isinstance(w, dict) and w.get("unit_key"))
        target_id = step.get("target_id")
        if target_id is not None and str(target_id) in by_id:
            units.add(by_id[str(target_id)])
        target_ids = step.get("target_ids")
        if isinstance(target_ids, list):
            units.update(by_id[str(x)] for x in target_ids if str(x) in by_id)
    return {x for x in units if x}


def conflicts_with_current_turn(command: str, plan: dict[str, object], explicit_units: set[str], widgets: list[dict[str, object]]) -> list[str]:
    conflicts: list[str] = []
    requested = explicit_action_families(command)
    families = plan_action_family(plan)

    # Restore is intentionally compiled as add_widget(s).
    expected = {"add" if action == "restore" else action for action in requested}
    if expected and families and not expected.issubset(families):
        conflicts.append(f"explicit actions {sorted(requested)} conflict with plan actions {sorted(families)}")

    targets = target_unit_keys(plan, widgets)
    if explicit_units and targets and not targets.issubset(explicit_units):
        conflicts.append(f"explicit units {sorted(explicit_units)} conflict with target units {sorted(targets)}")
    return conflicts
