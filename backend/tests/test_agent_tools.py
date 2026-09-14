import pytest

from app.agent_tools import (
    ToolContext,
    ToolDefinition,
    ToolEffect,
    ToolExecutionError,
    ToolParameter,
    ToolRegistry,
)
from app.refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind, UnitScope


def _refinery() -> RefineryScope:
    return RefineryScope(
        id="site-1",
        name="Refinery",
        standalone_units=(UnitScope("fcc", "FCC"), UnitScope("hcu", "HCU")),
    )


def _context(*, domains=frozenset({DataDomain.PROCESS}), units=frozenset({"fcc"})) -> ToolContext:
    return ToolContext(
        actor_id="engineer-1",
        refinery=_refinery(),
        access=AccessGrant(domains=domains, unit_ids=units),
        scope_kind=ScopeKind.UNIT,
        scope_id="fcc",
    )


@pytest.mark.asyncio
async def test_executes_authorized_read_only_tool_with_provenance():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo_process",
            description="test",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
            parameters=(ToolParameter("value", "string"),),
        ),
        lambda context, args: {"actor": context.actor_id, "value": args["value"]},
    )

    result = await registry.execute(
        "echo_process", context=_context(), arguments={"value": "ok"}
    )

    assert result.ok is True
    assert result.data == {"actor": "engineer-1", "value": "ok"}
    assert result.provenance["scope_id"] == "fcc"
    assert result.effect == ToolEffect.READ_ONLY


@pytest.mark.asyncio
async def test_rejects_tool_without_domain_authorization():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="search_archive",
            description="test",
            domain=DataDomain.KNOWLEDGE,
            effect=ToolEffect.READ_ONLY,
        ),
        lambda _context, _args: [],
    )

    with pytest.raises(ToolExecutionError, match="not authorized for knowledge"):
        await registry.execute("search_archive", context=_context(), arguments={})


@pytest.mark.asyncio
async def test_rejects_tool_outside_authorized_unit_scope():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="read_process",
            description="test",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
        ),
        lambda _context, _args: {},
    )
    context = ToolContext(
        actor_id="engineer-1",
        refinery=_refinery(),
        access=AccessGrant(domains=frozenset({DataDomain.PROCESS}), unit_ids=frozenset({"hcu"})),
        scope_kind=ScopeKind.UNIT,
        scope_id="fcc",
    )

    with pytest.raises(ToolExecutionError, match="not authorized for unit scope fcc"):
        await registry.execute("read_process", context=context, arguments={})


@pytest.mark.asyncio
async def test_validates_required_and_unknown_arguments_before_handler_runs():
    called = False

    def handler(_context, _args):
        nonlocal called
        called = True
        return {}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="validated",
            description="test",
            domain=DataDomain.PROCESS,
            effect=ToolEffect.READ_ONLY,
            parameters=(ToolParameter("tag", "string"),),
        ),
        handler,
    )

    with pytest.raises(ToolExecutionError, match="Missing required"):
        await registry.execute("validated", context=_context(), arguments={})
    with pytest.raises(ToolExecutionError, match="Unknown argument"):
        await registry.execute(
            "validated", context=_context(), arguments={"tag": "x", "surprise": True}
        )
    assert called is False


def test_duplicate_tool_registration_is_rejected():
    registry = ToolRegistry()
    definition = ToolDefinition(
        name="same",
        description="test",
        domain=DataDomain.PROCESS,
        effect=ToolEffect.READ_ONLY,
    )
    registry.register(definition, lambda _context, _args: None)

    with pytest.raises(ToolExecutionError, match="already registered"):
        registry.register(definition, lambda _context, _args: None)
