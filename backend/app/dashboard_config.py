from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

from .site_model import SiteModel

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
    values = [str(widget.get("id", "")), str(widget.get("title", "")), str(widget.get("type", ""))]
    tag_keys = widget.get("tag_keys")
    if isinstance(tag_keys, list):
        values.extend(str(item) for item in tag_keys)
    return " ".join(values).casefold()


def _match_widget(query: str, widgets: list[dict[str, object]], site: SiteModel) -> dict[str, object] | None:
    needle = query.casefold().strip()
    if not needle:
        return None

    type_terms = {
        "summary": ("summary", "σύνοψη", "συνοψη", "overview"),
        "average": ("average", "avg", "μέσο", "μεσο"),
        "trend": ("trend", "chart", "γράφημα", "γραφημα"),
        "kpi": ("kpi", "τιμή", "τιμη", "value"),
    }
    requested_type = next((key for key, terms in type_terms.items() if _contains_any(needle, terms)), None)

    tag_terms: list[str] = []
    for unit in site.units:
        for tag in unit.tags:
            candidates = (tag.key, tag.label, *tag.aliases)
            if any(candidate.casefold() in needle for candidate in candidates):
                tag_terms.append(tag.key.casefold())

    scored: list[tuple[int, dict[str, object]]] = []
    for widget in widgets:
        haystack = _widget_haystack(widget)
        score = 0
        if requested_type and str(widget.get("type", "")).casefold() == requested_type:
            score += 5
        for tag_key in tag_terms:
            if tag_key in haystack:
                score += 7
        title = str(widget.get("title", "")).casefold()
        if title and (title in needle or needle in title):
            score += 9
        if score:
            scored.append((score, widget))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def plan_dashboard_command(
    command: str,
    site: SiteModel,
    current_widgets: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    text = command.strip().casefold()
    if not text:
        raise DashboardCommandError("Command is empty")

    widgets = current_widgets or []
    is_layout_command = _contains_any(text, (
        "μετακίνησε", "μετακινησε", "βάλε", "βαλε", "τοποθέτησε", "τοποθετησε",
        "χώρεσε", "χωρεσε", "move", "place", "resize", "μέγεθος", "μεγεθος",
    ))

    if is_layout_command and widgets:
        if "ανάμεσα" in text or "αναμεσα" in text or "between" in text:
            separator = "ανάμεσα" if "ανάμεσα" in text else "αναμεσα" if "αναμεσα" in text else "between"
            before_between, after_between = text.split(separator, 1)
            connector = " και " if " και " in after_between else " and " if " and " in after_between else None
            if connector:
                first_ref, second_ref = after_between.split(connector, 1)
                target = _match_widget(before_between, widgets, site)
                first = _match_widget(first_ref, widgets, site)
                second = _match_widget(second_ref, widgets, site)
                if target and first and second:
                    return {
                        "action": "move_between",
                        "target_id": target.get("id"),
                        "first_id": first.get("id"),
                        "second_id": second.get("id"),
                        "requires_confirmation": False,
                        "read_only": True,
                    }

        target = _match_widget(text, widgets, site)
        if target:
            if _contains_any(text, ("μικρό", "μικρο", "compact", "small")):
                return {"action": "resize_widget", "target_id": target.get("id"), "width": 4, "height": "compact", "requires_confirmation": False, "read_only": True}
            if _contains_any(text, ("μεγάλο", "μεγαλο", "wide", "full", "πλάτος", "πλατος")):
                return {"action": "resize_widget", "target_id": target.get("id"), "width": 12, "height": "tall", "requires_confirmation": False, "read_only": True}

    unit = next((u for u in site.units if u.key.casefold() in text or u.name.casefold() in text), None)
    if unit is None and len(site.units) == 1:
        unit = site.units[0]
    if unit is None:
        raise DashboardCommandError("Could not resolve process unit")

    resolved = []
    for tag in unit.tags:
        candidates = (tag.key, tag.label, *tag.aliases)
        if any(candidate.casefold() in text for candidate in candidates):
            resolved.append(tag)

    if _contains_any(text, ("γράφημα", "γραφημα", "trend", "chart")):
        widget_type: WidgetType = "trend"
    elif _contains_any(text, ("μέσο όρο", "μεσο ορο", "average", "avg")):
        widget_type = "average"
    elif _contains_any(text, ("σύνοψη", "συνοψη", "summary", "overview")):
        widget_type = "summary"
    else:
        widget_type = "kpi"

    if widget_type != "summary" and not resolved:
        raise DashboardCommandError("Could not resolve any tag from command")

    period = "8h"
    for value in ("1h", "2h", "4h", "8h", "12h", "24h", "48h"):
        if value in text:
            period = value
            break

    title = {
        "trend": " / ".join(tag.label for tag in resolved),
        "average": f"Average {resolved[0].label}" if resolved else "Average",
        "summary": f"{unit.name} Summary",
        "kpi": resolved[0].label if resolved else unit.name,
    }[widget_type]

    tag_keys = tuple(tag.key for tag in resolved)
    return {
        "action": "add_widget",
        "widget": asdict(DashboardWidget(
            id=f"{unit.key}-{widget_type}-{'-'.join(tag_keys) or 'summary'}",
            type=widget_type,
            title=title,
            unit_key=unit.key,
            tag_keys=tag_keys,
            period=period,
            layout=_default_layout(widget_type, len(widgets)),
        )),
        "requires_confirmation": False,
        "read_only": True,
    }
