"""Refinery-wide hierarchy and governed data-domain model.

This module deliberately contains no plant writes and no external-service calls.
It defines the scalable scope/authorization vocabulary used by future connectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable


class ScopeKind(StrEnum):
    REFINERY = "refinery"
    COMPLEX = "complex"
    UNIT = "unit"


class DataDomain(StrEnum):
    PROCESS = "process"
    LABORATORY = "laboratory"
    KNOWLEDGE = "knowledge"
    PRODUCTION = "production"
    ENERGY = "energy"
    RELIABILITY = "reliability"
    INVENTORY = "inventory"
    MOVEMENTS = "movements"
    ECONOMICS = "economics"


@dataclass(frozen=True)
class UnitScope:
    id: str
    name: str


@dataclass(frozen=True)
class ComplexScope:
    id: str
    name: str
    units: tuple[UnitScope, ...] = ()


@dataclass(frozen=True)
class RefineryScope:
    id: str
    name: str
    complexes: tuple[ComplexScope, ...] = ()
    standalone_units: tuple[UnitScope, ...] = ()

    def unit_ids(self) -> set[str]:
        result = {unit.id for unit in self.standalone_units}
        for complex_scope in self.complexes:
            result.update(unit.id for unit in complex_scope.units)
        return result

    def complex_ids(self) -> set[str]:
        return {complex_scope.id for complex_scope in self.complexes}


@dataclass(frozen=True)
class AccessGrant:
    """Backend-enforced authorization grant.

    Economics is intentionally just another explicit domain; holding refinery
    scope does not imply economics access.
    """

    domains: frozenset[DataDomain]
    refinery_ids: frozenset[str] = field(default_factory=frozenset)
    complex_ids: frozenset[str] = field(default_factory=frozenset)
    unit_ids: frozenset[str] = field(default_factory=frozenset)

    def permits_domain(self, domain: DataDomain) -> bool:
        return domain in self.domains

    def permits_scope(
        self,
        refinery: RefineryScope,
        *,
        scope_kind: ScopeKind,
        scope_id: str,
    ) -> bool:
        if refinery.id in self.refinery_ids:
            return True

        if scope_kind == ScopeKind.REFINERY:
            return False

        if scope_kind == ScopeKind.COMPLEX:
            return scope_id in self.complex_ids

        if scope_id in self.unit_ids:
            return True

        for complex_scope in refinery.complexes:
            if complex_scope.id in self.complex_ids and any(
                unit.id == scope_id for unit in complex_scope.units
            ):
                return True
        return False

    def permits(
        self,
        refinery: RefineryScope,
        *,
        domain: DataDomain,
        scope_kind: ScopeKind,
        scope_id: str,
    ) -> bool:
        return self.permits_domain(domain) and self.permits_scope(
            refinery, scope_kind=scope_kind, scope_id=scope_id
        )


def default_engineering_domains() -> frozenset[DataDomain]:
    """Safe default set for engineering roles; economics is excluded."""

    return frozenset(
        {
            DataDomain.PROCESS,
            DataDomain.LABORATORY,
            DataDomain.KNOWLEDGE,
            DataDomain.PRODUCTION,
            DataDomain.ENERGY,
            DataDomain.RELIABILITY,
        }
    )


def domain_names(domains: Iterable[DataDomain]) -> list[str]:
    return sorted(domain.value for domain in domains)
