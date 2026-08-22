from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class UnitTag:
    key: str
    label: str
    unit: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcessUnit:
    key: str
    name: str
    tags: tuple[UnitTag, ...] = ()


@dataclass(frozen=True)
class SiteModel:
    name: str
    units: tuple[ProcessUnit, ...] = ()

    def list_units(self) -> list[dict[str, object]]:
        return [asdict(unit) for unit in self.units]

    def find_unit(self, query: str) -> ProcessUnit | None:
        needle = query.strip().casefold()
        for unit in self.units:
            if needle in {unit.key.casefold(), unit.name.casefold()}:
                return unit
        return None

    def resolve_tag(self, unit_key: str, query: str) -> UnitTag | None:
        unit = self.find_unit(unit_key)
        if unit is None:
            return None
        needle = query.strip().casefold()
        for tag in unit.tags:
            candidates = {tag.key.casefold(), tag.label.casefold(), *(alias.casefold() for alias in tag.aliases)}
            if needle in candidates:
                return tag
        return None


def default_site_model() -> SiteModel:
    # Development catalog only. Real PI WebIds/tags are configured locally and never committed.
    return SiteModel(
        name="Refinery",
        units=(
            ProcessUnit(
                key="fcc",
                name="FCC",
                tags=(
                    UnitTag("feed_flow", "Feed Flow", "m3/h", ("feed", "τροφοδοσία", "τροφοδοσια")),
                    UnitTag("reactor_temp", "Reactor Temperature", "C", ("reactor temperature", "θερμοκρασία reactor", "θερμοκρασια reactor")),
                    UnitTag("regenerator_temp", "Regenerator Temperature", "C", ("regenerator temperature", "θερμοκρασία regenerator", "θερμοκρασια regenerator")),
                    UnitTag("regenerator_o2", "Regenerator O2", "%", ("o2", "οξυγόνο regenerator", "οξυγονο regenerator")),
                ),
            ),
        ),
    )


def _site_from_payload(payload: dict[str, object]) -> SiteModel:
    name = str(payload.get("name") or "Refinery").strip() or "Refinery"
    raw_units = payload.get("units")
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("Site configuration must contain at least one unit")

    units: list[ProcessUnit] = []
    seen_units: set[str] = set()
    for raw_unit in raw_units:
        if not isinstance(raw_unit, dict):
            raise ValueError("Each site unit must be an object")
        key = str(raw_unit.get("key") or "").strip().casefold()
        unit_name = str(raw_unit.get("name") or key).strip()
        if not key or key in seen_units:
            raise ValueError("Each unit requires a unique non-empty key")
        seen_units.add(key)

        raw_tags = raw_unit.get("tags") or []
        if not isinstance(raw_tags, list):
            raise ValueError(f"Unit {key} tags must be a list")
        tags: list[UnitTag] = []
        seen_tags: set[str] = set()
        for raw_tag in raw_tags:
            if not isinstance(raw_tag, dict):
                raise ValueError(f"Unit {key} contains an invalid tag definition")
            tag_key = str(raw_tag.get("key") or "").strip()
            label = str(raw_tag.get("label") or tag_key).strip()
            engineering_unit = str(raw_tag.get("unit") or "").strip()
            aliases_value = raw_tag.get("aliases") or []
            if not isinstance(aliases_value, list):
                raise ValueError(f"Aliases for {key}.{tag_key} must be a list")
            if not tag_key or tag_key in seen_tags:
                raise ValueError(f"Unit {key} requires unique non-empty tag keys")
            seen_tags.add(tag_key)
            tags.append(UnitTag(tag_key, label, engineering_unit, tuple(str(item) for item in aliases_value)))

        units.append(ProcessUnit(key=key, name=unit_name, tags=tuple(tags)))

    return SiteModel(name=name, units=tuple(units))


def load_site_model(config_path: str | Path | None = None) -> SiteModel:
    """Load the semantic refinery/unit catalog from a local JSON file.

    Real site/tag metadata is intentionally not committed to the repository.
    Set FCC_SITE_CONFIG to a local JSON file to configure one or many units.
    When no file is configured, the safe development FCC catalog is used.
    """
    configured = config_path or os.environ.get("FCC_SITE_CONFIG")
    if not configured:
        return default_site_model()

    path = Path(configured).expanduser()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Site configuration root must be an object")
    return _site_from_payload(payload)
