from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from .site_model import ProcessUnit, SiteModel, UnitTag

WidgetType = Literal["kpi", "trend", "average", "summary"]


@dataclass(frozen=True)
class WidgetLayout:
    order: int = 0
    width: int = 6
    height: str = "normal"


@dataclass(frozen=True)
class DashboardWidget:
    id: str
    type: WidgetType
    title: str
    unit_key: str
    tag_keys: tuple[str, ...] = ()
    period: str = "8h"
    layout: WidgetLayout = field(default_factory=WidgetLayout)


@dataclass
class DashboardPage:
    key: str
    title: str
    widgets: list[DashboardWidget] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"key": self.key, "title": self.title, "widgets": [asdict(w) for w in self.widgets]}


class DashboardCommandError(ValueError):
    pass


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _default_layout(widget_type: WidgetType, order: int) -> WidgetLayout:
    if widget_type == "trend":
        return WidgetLayout(order=order, width=12, height="tall")
    if widget_type == "summary":
        return WidgetLayout(order=order, width=6, height="normal")
    return WidgetLayout(order=order, width=4, height="compact")


def _widget_haystack(widget: dict[str, object]) -> str:
    values = [str(widget.get("id", "")), str(widget.get("title", "")), str(widget.get("type", "")), str(widget.get("unit_key", ""))]
    tag_keys = widget.get("tag_keys")
    if isinstance(tag_keys, (list, tuple)):
        values.extend(str(item) for item in tag_keys)
    return " ".join(values).casefold()


def _match_widget(query: str, widgets: list[dict[str, object]], site: SiteModel) -> dict[str, object] | None:
    needle = query.casefold().strip()
    if not needle:
        return None

    type_terms = {
        "summary": ("summary", "σύνοψη", "συνοψη", "overview"),
        "average": ("average", "avg", "μέσο", "μεσο"),
        "trend": ("trend", "chart", "γράφημα", "γραφημα", "διάγραμμα", "διαγραμμα"),
        "kpi": ("kpi", "τιμή", "τιμη", "value"),
    }
    requested_type = next((key for key, terms in type_terms.items() if _contains_any(needle, terms)), None)

    requested_units = {
        unit.key.casefold()
        for unit in site.units
        if any(candidate.casefold() in needle for candidate in (unit.key, unit.name) if candidate)
    }
    tag_terms: list[str] = []
    for unit in site.units:
        for tag in unit.tags:
            candidates = (tag.key, tag.label, tag.semantic, *tag.aliases)
            if any(candidate.casefold() in needle for candidate in candidates if candidate):
                tag_terms.append(tag.key.casefold())

    scored: list[tuple[int, dict[str, object]]] = []
    for widget in widgets:
        haystack = _widget_haystack(widget)
        score = 0
        widget_unit = str(widget.get("unit_key", "")).casefold()
        if requested_units:
            if widget_unit in requested_units:
                score += 12
            else:
                score -= 8
        if requested_type and str(widget.get("type", "")).casefold() == requested_type:
            score += 5
        for tag_key in tag_terms:
            if tag_key in haystack:
                score += 7
        title = str(widget.get("title", "")).casefold()
        if title and (title in needle or needle in title):
            score += 9
        if score > 0:
            scored.append((score, widget))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _mentioned_units(text: str, site: SiteModel) -> list[ProcessUnit]:
    mentions: list[tuple[int, ProcessUnit]] = []
    for unit in site.units:
        positions = [position for candidate in (unit.key.casefold(), unit.name.casefold()) if candidate and (position := text.find(candidate)) >= 0]
        if positions:
            mentions.append((min(positions), unit))
    mentions.sort(key=lambda item: item[0])
    return [unit for _, unit in mentions]


def _resolve_tags(unit: ProcessUnit, text: str) -> list[UnitTag]:
    resolved: list[UnitTag] = []
    for tag in unit.tags:
        candidates = (tag.key, tag.label, tag.semantic, *tag.aliases)
        if any(candidate.casefold() in text for candidate in candidates if candidate):
            resolved.append(tag)
    return resolved


def _widget_type(text: str) -> WidgetType:
    if _contains_any(text, ("γράφημα", "γραφημα", "διάγραμμα", "διαγραμμα", "trend", "chart")):
        return "trend"
    if _contains_any(text, ("μέσο όρο", "μεσο ορο", "average", "avg")):
        return "average"
    if _contains_any(text, ("σύνοψη", "συνοψη", "summary", "overview")):
        return "summary"
    return "kpi"


def _period(text: str) -> str:
    for value in ("1h", "2h", "4h", "8h", "12h", "24h", "48h"):
        if value in text:
            return value
    return "8h"


def _build_widgets_for_unit(unit: ProcessUnit, text: str, widget_type: WidgetType, period: str, start_order: int) -> list[dict[str, object]]:
    resolved = _resolve_tags(unit, text)
    if widget_type != "summary" and not resolved:
        return []
    if widget_type == "summary":
        return [asdict(DashboardWidget(id=f"{unit.key}-summary-summary", type="summary", title=f"{unit.name} Summary", unit_key=unit.key, tag_keys=(), period=period, layout=_default_layout("summary", start_order)))]
    if widget_type == "trend":
        tag_keys = tuple(tag.key for tag in resolved)
        return [asdict(DashboardWidget(id=f"{unit.key}-trend-{'-'.join(tag_keys)}", type="trend", title=" / ".join(tag.label for tag in resolved), unit_key=unit.key, tag_keys=tag_keys, period=period, layout=_default_layout("trend", start_order)))]
    created: list[dict[str, object]] = []
    for offset, tag in enumerate(resolved):
        title = f"Average {tag.label}" if widget_type == "average" else tag.label
        created.append(asdict(DashboardWidget(id=f"{unit.key}-{widget_type}-{tag.key}", type=widget_type, title=title, unit_key=unit.key, tag_keys=(tag.key,), period=period, layout=_default_layout(widget_type, start_order + offset))))
    return created


def _clone_unit_widgets(source: ProcessUnit, targets: list[ProcessUnit], current_widgets: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[str]]:
    source_widgets = [widget for widget in current_widgets if str(widget.get("unit_key", "")).casefold() == source.key.casefold()]
    if not source_widgets:
        raise DashboardCommandError(f"No existing widgets found for {source.name}")
    cloned: list[dict[str, object]] = []
    warnings: list[str] = []
    source_by_key = {tag.key: tag for tag in source.tags}
    for target in targets:
        for source_widget in source_widgets:
            widget_type = str(source_widget.get("type", "kpi"))
            if widget_type not in {"kpi", "trend", "average", "summary"}:
                continue
            raw_tag_keys = source_widget.get("tag_keys")
            source_tag_keys = [str(value) for value in raw_tag_keys] if isinstance(raw_tag_keys, (list, tuple)) else []
            target_tag_keys: list[str] = []
            target_labels: list[str] = []
            missing_semantics: list[str] = []
            for source_tag_key in source_tag_keys:
                source_tag = source_by_key.get(source_tag_key)
                if source_tag is None:
                    missing_semantics.append(source_tag_key); continue
                target_tag = target.tag_by_semantic(source_tag.semantic)
                if target_tag is None:
                    missing_semantics.append(source_tag.semantic); continue
                target_tag_keys.append(target_tag.key); target_labels.append(target_tag.label)
            if source_tag_keys and not target_tag_keys:
                warnings.append(f"{target.name}: could not map {', '.join(missing_semantics)}"); continue
            if missing_semantics:
                warnings.append(f"{target.name}: partial mapping; missing {', '.join(missing_semantics)}")
            if widget_type == "summary": title, suffix = f"{target.name} Summary", "summary"
            elif widget_type == "trend": title, suffix = " / ".join(target_labels), "-".join(target_tag_keys)
            elif widget_type == "average": title, suffix = (f"Average {target_labels[0]}" if target_labels else f"{target.name} Average"), (target_tag_keys[0] if target_tag_keys else "average")
            else: title, suffix = (target_labels[0] if target_labels else target.name), (target_tag_keys[0] if target_tag_keys else "kpi")
            source_layout = source_widget.get("layout")
            layout = WidgetLayout(order=len(current_widgets) + len(cloned), width=int(source_layout.get("width", 6)), height=str(source_layout.get("height", "normal"))) if isinstance(source_layout, dict) else _default_layout(widget_type, len(current_widgets) + len(cloned))  # type: ignore[arg-type]
            cloned.append(asdict(DashboardWidget(id=f"{target.key}-{widget_type}-{suffix}", type=widget_type, title=title, unit_key=target.key, tag_keys=tuple(target_tag_keys), period=str(source_widget.get("period", "8h")), layout=layout)))  # type: ignore[arg-type]
    return cloned, warnings


def plan_dashboard_command(command: str, site: SiteModel, current_widgets: list[dict[str, object]] | None = None) -> dict[str, object]:
    text = command.strip().casefold()
    if not text:
        raise DashboardCommandError("Command is empty")
    widgets = current_widgets or []
    mentioned_units = _mentioned_units(text, site)

    remove_requested = _contains_any(text, ("αφαίρεσε", "αφαιρεσε", "βγάλε", "βγαλε", "διέγραψε", "διεγραψε", "remove", "delete"))
    if remove_requested:
        if not widgets:
            raise DashboardCommandError("There are no widgets to remove")
        target = _match_widget(text, widgets, site)
        if target is None:
            raise DashboardCommandError("Could not resolve which widget to remove")
        return {"action": "remove_widget", "target_id": target.get("id"), "requires_confirmation": False, "read_only": True}

    clone_requested = _contains_any(text, ("τα ίδια", "τα ιδια", "το ίδιο", "το ιδιο", "ίδιο με", "ιδιο με", "same as", "same for", "copy"))
    if clone_requested and len(mentioned_units) >= 2:
        source, targets = mentioned_units[0], mentioned_units[1:]
        cloned, warnings = _clone_unit_widgets(source, targets, widgets)
        if not cloned:
            raise DashboardCommandError("No compatible widgets could be cloned to the requested unit")
        return {"action": "add_widgets", "widgets": cloned, "source_unit": source.key, "target_units": [unit.key for unit in targets], "warnings": warnings, "requires_confirmation": False, "read_only": True}

    is_layout_command = _contains_any(text, ("μετακίνησε", "μετακινησε", "τοποθέτησε", "τοποθετησε", "χώρεσε", "χωρεσε", "move", "place", "resize", "μέγεθος", "μεγεθος"))
    if is_layout_command and widgets:
        if "ανάμεσα" in text or "αναμεσα" in text or "between" in text:
            separator = "ανάμεσα" if "ανάμεσα" in text else "αναμεσα" if "αναμεσα" in text else "between"
            before_between, after_between = text.split(separator, 1)
            connector = " και " if " και " in after_between else " and " if " and " in after_between else None
            if connector:
                first_ref, second_ref = after_between.split(connector, 1)
                target, first, second = _match_widget(before_between, widgets, site), _match_widget(first_ref, widgets, site), _match_widget(second_ref, widgets, site)
                if target and first and second:
                    return {"action": "move_between", "target_id": target.get("id"), "first_id": first.get("id"), "second_id": second.get("id"), "requires_confirmation": False, "read_only": True}
        target = _match_widget(text, widgets, site)
        if target:
            if _contains_any(text, ("μικρό", "μικρο", "compact", "small")):
                return {"action": "resize_widget", "target_id": target.get("id"), "width": 4, "height": "compact", "requires_confirmation": False, "read_only": True}
            if _contains_any(text, ("μεγάλο", "μεγαλο", "wide", "full", "πλάτος", "πλατος")):
                return {"action": "resize_widget", "target_id": target.get("id"), "width": 12, "height": "tall", "requires_confirmation": False, "read_only": True}

    if not mentioned_units:
        if len(site.units) == 1:
            mentioned_units = [site.units[0]]
        else:
            raise DashboardCommandError("Could not resolve process unit")
    widget_type, period = _widget_type(text), _period(text)
    planned_widgets: list[dict[str, object]] = []
    unresolved_units: list[str] = []
    for unit in mentioned_units:
        unit_widgets = _build_widgets_for_unit(unit, text, widget_type, period, len(widgets) + len(planned_widgets))
        if unit_widgets: planned_widgets.extend(unit_widgets)
        else: unresolved_units.append(unit.name)
    if not planned_widgets:
        raise DashboardCommandError("Could not resolve any tag from command")
    result: dict[str, object] = {"requires_confirmation": False, "read_only": True}
    if unresolved_units:
        result["warnings"] = [f"No matching variables found for {name}" for name in unresolved_units]
    result.update({"action": "add_widget", "widget": planned_widgets[0]} if len(planned_widgets) == 1 else {"action": "add_widgets", "widgets": planned_widgets})
    return result
