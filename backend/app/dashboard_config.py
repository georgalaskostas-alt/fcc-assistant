from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

from .site_model import SiteModel

WidgetType = Literal["kpi", "trend", "average", "summary"]


@dataclass(frozen=True)
class DashboardWidget:
    id: str
    type: WidgetType
    title: str
    unit_key: str
    tag_keys: tuple[str, ...] = ()
    period: str = "8h"


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


def plan_dashboard_command(command: str, site: SiteModel) -> dict[str, object]:
    text = command.strip().casefold()
    if not text:
        raise DashboardCommandError("Command is empty")

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
        )),
        "requires_confirmation": False,
        "read_only": True,
    }
