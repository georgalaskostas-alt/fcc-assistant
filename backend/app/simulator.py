from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sin
from typing import Any


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
    """Deterministic synthetic FCC data for development only."""

    def list_tags(self) -> list[dict[str, Any]]:
        return [{"key": t.key, "name": t.name, "group": t.group, "unit": t.unit} for t in SIMULATED_TAGS]

    def recorded_values(self, key: str, start: datetime, end: datetime, step_minutes: int = 15) -> dict[str, Any]:
        tag = next((t for t in SIMULATED_TAGS if t.key == key), None)
        if tag is None:
            raise KeyError(key)
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
            # Deliberate synthetic event for demo analysis after 4 hours.
            if hours >= 4.0:
                if key == "regen_temp":
                    event = min((hours - 4.0) * 1.8, 9.0)
                elif key == "regen_o2":
                    event = -min((hours - 4.0) * 0.08, 0.4)
                elif key == "lcco_rate":
                    event = -min((hours - 4.0) * 0.45, 2.5)
            value = tag.base + wave + tag.drift_per_hour * hours + event
            items.append({"Timestamp": current.isoformat().replace("+00:00", "Z"), "Value": round(value, 4)})
            current += timedelta(minutes=step_minutes)
            index += 1
        return {"Items": items}

    def demo_shift(self) -> dict[str, Any]:
        start = datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 19, 15, 0, tzinfo=timezone.utc)
        return {tag.key: self.recorded_values(tag.key, start, end) for tag in SIMULATED_TAGS}
