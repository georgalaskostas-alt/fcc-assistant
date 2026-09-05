from app.refinery_model import (
    AccessGrant,
    ComplexScope,
    DataDomain,
    RefineryScope,
    ScopeKind,
    UnitScope,
    default_engineering_domains,
)


def sample_refinery() -> RefineryScope:
    return RefineryScope(
        id="refinery-1",
        name="Example Refinery",
        complexes=(
            ComplexScope(
                id="conversion",
                name="Conversion Complex",
                units=(
                    UnitScope(id="fcc", name="FCC"),
                    UnitScope(id="hcu", name="Hydrocracker"),
                    UnitScope(id="vdu", name="Vacuum Distillation"),
                ),
            ),
        ),
    )


def test_complex_grant_covers_its_units_but_not_refinery_scope():
    refinery = sample_refinery()
    grant = AccessGrant(
        domains=default_engineering_domains(),
        complex_ids=frozenset({"conversion"}),
    )

    assert grant.permits(
        refinery,
        domain=DataDomain.PROCESS,
        scope_kind=ScopeKind.UNIT,
        scope_id="hcu",
    )
    assert not grant.permits(
        refinery,
        domain=DataDomain.PROCESS,
        scope_kind=ScopeKind.REFINERY,
        scope_id="refinery-1",
    )


def test_economics_requires_explicit_domain_permission():
    refinery = sample_refinery()
    manager = AccessGrant(
        domains=default_engineering_domains(),
        refinery_ids=frozenset({"refinery-1"}),
    )

    assert manager.permits(
        refinery,
        domain=DataDomain.PRODUCTION,
        scope_kind=ScopeKind.REFINERY,
        scope_id="refinery-1",
    )
    assert not manager.permits(
        refinery,
        domain=DataDomain.ECONOMICS,
        scope_kind=ScopeKind.REFINERY,
        scope_id="refinery-1",
    )

    economics_manager = AccessGrant(
        domains=manager.domains | {DataDomain.ECONOMICS},
        refinery_ids=manager.refinery_ids,
    )
    assert economics_manager.permits(
        refinery,
        domain=DataDomain.ECONOMICS,
        scope_kind=ScopeKind.REFINERY,
        scope_id="refinery-1",
    )


def test_single_unit_engineer_does_not_gain_sibling_unit_access():
    refinery = sample_refinery()
    grant = AccessGrant(
        domains=default_engineering_domains(),
        unit_ids=frozenset({"fcc"}),
    )

    assert grant.permits(
        refinery,
        domain=DataDomain.LABORATORY,
        scope_kind=ScopeKind.UNIT,
        scope_id="fcc",
    )
    assert not grant.permits(
        refinery,
        domain=DataDomain.LABORATORY,
        scope_kind=ScopeKind.UNIT,
        scope_id="hcu",
    )
