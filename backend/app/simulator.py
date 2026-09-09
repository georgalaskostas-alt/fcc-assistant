from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sin
from typing import Any

from .site_model import SiteModel, load_site_model


@dataclass(frozen=True)
class SimulatedTag:
    key: str
    name: str
    group: str
    unit: str
    base: float
    amplitude: float
    drift_per_hour: float = 0.0


SIMULATED_TAGS = [
    SimulatedTag("feed_flow", "Feed Flow", "feed", "m3/h", 265.0, 4.0, 0.15),
    SimulatedTag("reactor_temp", "Reactor Temperature", "reactor", "C", 527.0, 1.8, 0.03),
    SimulatedTag("regen_temp", "Regenerator Temperature", "regenerator", "C", 696.0, 2.5, 0.10),
    SimulatedTag("regen_o2", "Regenerator O2", "regenerator", "%", 1.9, 0.25, -0.01),
    SimulatedTag("fractionator_dp", "Main Fractionator DP", "main_fractionator", "bar", 0.42, 0.03, 0.002),
    SimulatedTag("naphtha_rate", "Naphtha Rate", "products", "m3/h", 78.0, 2.2, 0.08),
    SimulatedTag("lcco_rate", "LCCO Rate", "products", "m3/h", 39.0, 1.4, -0.04),
]


class SimulatedFCCSource:
    """Deterministic synthetic FCC data for development only.

    Kept for backwards-compatible tests and direct FCC simulator usage.
    The desktop API now uses SimulatedSiteSource for multi-unit workspaces.
    """

    def list_tags(self) -> list[dict[str, Any]]:
        return [{"key": t.key, "name": t.name, "group": t.group, "unit": t.unit} for t in SIMULATED_TAGS]

    def recorded_values(self, key: str, start: datetime, end: datetime, step_minutes: int = 15) -> dict[str, Any]:
        tag = next((t for t in SIMULATED_TAGS if t.key == key), None)
        if tag is None:
            raise KeyError(key)
        return _series(tag, key, start, end, step_minutes)

    def demo_shift(self) -> dict[str, Any]:
        start = datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)
        return {tag.key: self.recorded_values(tag.key, start, end) for tag in SIMULATED_TAGS}


@dataclass(frozen=True)
class SiteSimulatedTag:
    key: str
    name: str
    group: str
    unit: str
    unit_key: str
    semantic_key: str
    base: float
    amplitude: float
    drift_per_hour: float = 0.0


SEMANTIC_PROFILES: dict[str, tuple[float, float, float]] = {
    "feed_flow": (265.0, 4.0, 0.15),
    "reaction_temperature": (527.0, 1.8, 0.03),
    "regenerator_temperature": (696.0, 2.5, 0.10),
    "regenerator_o2": (1.9, 0.25, -0.01),
    "fractionator_dp": (0.42, 0.03, 0.002),
    "naphtha_rate": (78.0, 2.2, 0.08),
    "lcco_rate": (39.0, 1.4, -0.04),
    "lab_quality": (94.0, 0.35, 0.0),
}


def _adjust_profile_for_unit(semantic: str, profile: tuple[float, float, float], unit_index: int) -> tuple[float, float, float]:
    base, amplitude, drift = profile
    if unit_index == 0:
        return profile

    if semantic.endswith("temperature"):
        base = base - 95.0 * unit_index
        amplitude = max(0.8, amplitude * (1.0 - 0.08 * unit_index))
    elif semantic.endswith("_o2"):
        base = max(0.5, base - 0.12 * unit_index)
    elif "flow" in semantic or semantic.endswith("_rate"):
        base = max(1.0, base * max(0.45, 1.0 - 0.22 * unit_index))
        amplitude = max(0.2, amplitude * max(0.5, 1.0 - 0.12 * unit_index))
    else:
        base = base * max(0.6, 1.0 - 0.08 * unit_index)
    return base, amplitude, drift


def _fallback_profile(semantic: str, unit_index: int) -> tuple[float, float, float]:
    seed = sum(ord(char) for char in semantic) or 1
    base = float(10 + seed % 90)
    amplitude = max(0.25, (seed % 11) / 5.0)
    drift = ((seed % 7) - 3) / 100.0
    return _adjust_profile_for_unit(semantic, (base, amplitude, drift), unit_index)


class SimulatedSiteSource:
    """Synthetic multi-unit data generated from the local semantic site catalog.

    This is development-only data. It never contacts PI and never performs writes.
    It lets the desktop exercise refinery-wide grouping, unit scopes and semantic
    cloning before a real local PI configuration is supplied.
    """

    def __init__(self, site: SiteModel | None = None) -> None:
        self.site = site or load_site_model()
        self._tags = self._build_tags()

    def _build_tags(self) -> list[SiteSimulatedTag]:
        result: list[SiteSimulatedTag] = []
        seen_keys: set[str] = set()
        for unit_index, process_unit in enumerate(self.site.units):
            for tag in process_unit.tags:
                if tag.key in seen_keys:
                    raise ValueError(f"Simulator requires globally unique site tag keys: {tag.key}")
                seen_keys.add(tag.key)
                semantic = tag.semantic
                profile = SEMANTIC_PROFILES.get(semantic)
                if profile is None:
                    base, amplitude, drift = _fallback_profile(semantic, unit_index)
                else:
                    base, amplitude, drift = _adjust_profile_for_unit(semantic, profile, unit_index)
                result.append(
                    SiteSimulatedTag(
                        key=tag.key,
                        name=tag.label,
                        group=process_unit.key,
                        unit=tag.unit,
                        unit_key=process_unit.key,
                        semantic_key=semantic,
                        base=base,
                        amplitude=amplitude,
                        drift_per_hour=drift,
                    )
                )
        return result

    def list_tags(self) -> list[dict[str, Any]]:
        return [
            {
                "key": tag.key,
                "name": tag.name,
                "group": tag.group,
                "unit": tag.unit,
                "unit_key": tag.unit_key,
                "semantic_key": tag.semantic_key,
            }
            for tag in self._tags
        ]

    def recorded_values(self, key: str, start: datetime, end: datetime, step_minutes: int = 15) -> dict[str, Any]:
        tag = next((item for item in self._tags if item.key == key), None)
        if tag is None:
            raise KeyError(key)
        return _series(tag, tag.semantic_key, start, end, step_minutes)

    def demo_shift(self) -> dict[str, Any]:
        start = datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)
        return {tag.key: self.recorded_values(tag.key, start, end) for tag in self._tags}


def _series(tag: Any, event_key: str, start: datetime, end: datetime, step_minutes: int) -> dict[str, Any]:
    if end <= start:
        raise ValueError("end must be after start")

    items = []
    current = start.astimezone(timezone.utc)
    origin = current
    index = 0
    while current <= end.astimezone(timezone.utc):
        hours = (current - origin).total_seconds() / 3600.0
        wave = sin(index / 2.2) * tag.amplitude
        event = 0.0
        if hours >= 4.0:
            if event_key in {"regen_temp", "regenerator_temperature"}:
                event = min((hours - 4.0) * 1.8, 9.0)
            elif event_key in {"regen_o2", "regenerator_o2"}:
                event = -min((hours - 4.0) * 0.08, 0.4)
            elif event_key == "lcco_rate":
                event = -min((hours - 4.0) * 0.45, 2.5)
        value = tag.base + wave + tag.drift_per_hour * hours + event
        items.append({"Timestamp": current.isoformat().replace("+00:00", "Z"), "Value": round(value, 4)})
        current += timedelta(minutes=step_minutes)
        index += 1
    return {"Items": items}
