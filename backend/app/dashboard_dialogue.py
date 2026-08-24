from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .dashboard_config import DashboardWidget, WidgetLayout
from .site_model import ProcessUnit, SiteModel


class DashboardDialogueStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "dashboard-dialogue.json")

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"workspaces": {}, "unit_aliases": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workspaces": {}, "unit_aliases": {}}
        return payload if isinstance(payload, dict) else {"workspaces": {}, "unit_aliases": {}}

    def _save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get_state(self, workspace: str) -> dict[str, object]:
        payload = self._load()
        workspaces = payload.get("workspaces")
        if not isinstance(workspaces, dict):
            return {}
        state = workspaces.get(workspace)
        return dict(state) if isinstance(state, dict) else {}

    def aliases(self) -> dict[str, str]:
        payload = self._load()
        raw = payload.get("unit_aliases")
        return {str(k).casefold(): str(v).casefold() for k, v in raw.items()} if isinstance(raw, dict) else {}

    def learn_alias(self, phrase: str, unit_key: str) -> None:
        alias = phrase.strip().casefold()
        if len(alias) < 2:
            return
        payload = self._load()
        raw = payload.setdefault("unit_aliases", {})
        if not isinstance(raw, dict):
            raw = {}
            payload["unit_aliases"] = raw
        raw[alias] = unit_key.strip().casefold()
        self._save(payload)

    def remember_requested_unit(self, workspace: str, unit_key: str) -> None:
        payload = self._load()
        workspaces = payload.setdefault("workspaces", {})
        if not isinstance(workspaces, dict):
            workspaces = {}
            payload["workspaces"] = workspaces
        state = dict(workspaces.get(workspace) or {})
        state["last_requested_unit_key"] = unit_key.strip().casefold()
        workspaces[workspace] = state
        self._save(payload)

    def remember(self, workspace: str, command: str, plan: dict[str, object], workspace_payload: dict[str, object], message: str | None = None) -> None:
        payload = self._load()
        workspaces = payload.setdefault("workspaces", {})
        if not isinstance(workspaces, dict):
            workspaces = {}
            payload["workspaces"] = workspaces
        state = dict(workspaces.get(workspace) or {})
        state["last_command"] = command
        state["last_action"] = str(plan.get("action", ""))
        if message:
            state["last_message"] = message
        action = str(plan.get("action", ""))
        candidate = plan.get("widget")
        if action == "add_widgets":
            widgets = plan.get("widgets")
            if isinstance(widgets, list) and widgets and isinstance(widgets[-1], dict):
                candidate = widgets[-1]
        elif action == "replace_widget":
            candidate = plan.get("widget")
        if isinstance(candidate, dict):
            state["last_widget"] = candidate
            state["last_unit_key"] = str(candidate.get("unit_key", ""))
        elif action == "remove_widget":
            state["last_removed_id"] = str(plan.get("target_id", ""))
        workspaces[workspace] = state
        self._save(payload)


def _unit_tokens(unit: ProcessUnit) -> tuple[str, ...]:
    aliases = list(getattr(unit, "aliases", ()))
    key = unit.key.casefold()
    name = unit.name.casefold()
    if key == "hcu" or name == "hcu":
        aliases.extend(("Hydrocracker", "hydro cracker", "hydrocracking", "υδροκράκερ", "υδροκρακερ"))
    if key == "vdu" or name == "vdu":
        aliases.extend(("Vacuum Distillation", "vacuum unit", "μονάδα κενού", "μοναδα κενου"))
    return tuple(dict.fromkeys([unit.key, unit.name, *aliases]))


def resolve_units(text: str, site: SiteModel, learned_aliases: dict[str, str] | None = None) -> list[ProcessUnit]:
    folded = text.casefold()
    matches: list[tuple[int, ProcessUnit]] = []
    learned_aliases = learned_aliases or {}
    for unit in site.units:
        positions = [folded.find(token.casefold()) for token in _unit_tokens(unit) if token and token.casefold() in folded]
        for alias, key in learned_aliases.items():
            if key == unit.key.casefold() and alias in folded:
                positions.append(folded.find(alias))
        if positions:
            matches.append((min(positions), unit))
    matches.sort(key=lambda item: item[0])
    return [unit for _, unit in matches]


def _retarget_widget(widget: dict[str, object], target: ProcessUnit, site: SiteModel) -> dict[str, object] | None:
    source_key = str(widget.get("unit_key", ""))
    source = site.find_unit(source_key)
    raw_tags = widget.get("tag_keys")
    source_tag_keys = [str(v) for v in raw_tags] if isinstance(raw_tags, (list, tuple)) else []
    target_tags: list[str] = []
    labels: list[str] = []
    if source and source_tag_keys:
        by_key = {tag.key: tag for tag in source.tags}
        for key in source_tag_keys:
            source_tag = by_key.get(key)
            if source_tag is None:
                return None
            mapped = target.tag_by_semantic(source_tag.semantic)
            if mapped is None:
                return None
            target_tags.append(mapped.key)
            labels.append(mapped.label)
    widget_type = str(widget.get("type", "kpi"))
    title = str(widget.get("title", target.name))
    if labels:
        title = " / ".join(labels) if widget_type == "trend" else (f"Average {labels[0]}" if widget_type == "average" else labels[0])
    suffix = "-".join(target_tags) if target_tags else "summary"
    raw_layout = widget.get("layout")
    layout = WidgetLayout(
        order=int(raw_layout.get("order", 0)),
        width=int(raw_layout.get("width", 6)),
        height=str(raw_layout.get("height", "normal")),
    ) if isinstance(raw_layout, dict) else WidgetLayout()
    return asdict(DashboardWidget(
        id=f"{target.key}-{widget_type}-{suffix}",
        type=widget_type,  # type: ignore[arg-type]
        title=title,
        unit_key=target.key,
        tag_keys=tuple(target_tags),
        period=str(widget.get("period", "8h")),
        layout=layout,
    ))


def contextual_plan(command: str, site: SiteModel, state: dict[str, object], current_widgets: list[dict[str, object]], learned_aliases: dict[str, str] | None = None) -> tuple[dict[str, object] | None, str | None]:
    text = command.strip().casefold()
    last_widget = state.get("last_widget") if isinstance(state.get("last_widget"), dict) else None
    units = resolve_units(text, site, learned_aliases)

    asks_where = any(token in text for token in ("πού", "που", "σε ποια μονάδα", "σε ποια μοναδα", "where")) and any(token in text for token in ("τελευτα", "γράφημα", "γραφημα", "διάγραμμα", "διαγραμμα", "widget"))
    if asks_where and last_widget:
        unit = site.find_unit(str(last_widget.get("unit_key", "")))
        unit_name = unit.name if unit else str(last_widget.get("unit_key", "")).upper()
        title = str(last_widget.get("title", "το τελευταίο γράφημα"))
        return {"action": "answer", "read_only": True, "requires_confirmation": False}, f"Το τελευταίο γράφημα, {title}, βρίσκεται στη μονάδα {unit_name}."

    refers_previous = any(token in text for token in ("το τελευταίο", "το τελευταιο", "που βάλαμε", "που βαλαμε", "αυτό", "αυτο", "το γράφημα", "το γραφημα", "το", "αυτό που έβαλες", "αυτο που εβαλες"))
    remove_intent = any(token in text for token in ("αφαίρε", "αφαιρε", "βγάλε", "βγαλε", "διέγρα", "διεγρα", "remove", "delete"))
    move_intent = any(token in text for token in ("βάλε", "βαλε", "μετέφερε", "μεταφερε", "πήγαιν", "πηγαιν", "άλλαξ", "αλλαξ", "move", "change"))
    correction = any(token in text for token in ("όχι", "οχι", "εννοώ", "εννοω", "λάθος", "λαθος", "έκανες λάθος", "εκανες λαθος", "διόρθ", "διορθ"))

    target: ProcessUnit | None = units[-1] if units else None
    if correction and target is None:
        requested_key = str(state.get("last_requested_unit_key", "")).strip()
        if requested_key:
            target = site.find_unit(requested_key)

    if last_widget and target and (correction or (remove_intent and move_intent) or (refers_previous and move_intent)):
        replacement = _retarget_widget(last_widget, target, site)
        if replacement is not None:
            current_unit = str(last_widget.get("unit_key", "")).casefold()
            if current_unit == target.key.casefold():
                return {"action": "answer", "read_only": True, "requires_confirmation": False}, f"Το τελευταίο γράφημα είναι ήδη στη μονάδα {target.name}."
            plan = {"action": "replace_widget", "target_id": last_widget.get("id"), "widget": replacement, "read_only": True, "requires_confirmation": False}
            return plan, f"Διόρθωσα το λάθος και μετέφερα το {replacement.get('title', 'γράφημα')} στη μονάδα {target.name}."

    if last_widget and correction and target is None:
        return {"action": "answer", "read_only": True, "requires_confirmation": False}, "Κατάλαβα ότι θέλεις να διορθώσω την προηγούμενη ενέργεια, αλλά δεν είμαι βέβαιος για τη σωστή μονάδα. Πες μου μόνο τη μονάδα και θα το διορθώσω."

    if last_widget and refers_previous and remove_intent:
        return {"action": "remove_widget", "target_id": last_widget.get("id"), "read_only": True, "requires_confirmation": False}, "Αφαίρεσα το τελευταίο γράφημα."

    return None, None
