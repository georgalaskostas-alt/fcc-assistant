from __future__ import annotations

from dataclasses import dataclass, field, asdict


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
