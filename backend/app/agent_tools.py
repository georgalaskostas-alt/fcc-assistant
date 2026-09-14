"""Generic governed tool registry for the refinery-wide AI assistant.

The LLM may select tools, but this layer validates arguments, authorization and
side-effect class before deterministic handlers are executed. Process-control
writes are intentionally unsupported by this contract.
"""

from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable

from .refinery_model import AccessGrant, DataDomain, RefineryScope, ScopeKind


class ToolEffect(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    CONTROLLED_DOCUMENT_PROPOSAL = "controlled_document_proposal"


class ToolExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolParameter:
    name: str
    type: str
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    domain: DataDomain
    effect: ToolEffect
    parameters: tuple[ToolParameter, ...] = ()
    requires_scope: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["domain"] = self.domain.value
        payload["effect"] = self.effect.value
        return payload


@dataclass(frozen=True)
class ToolContext:
    actor_id: str
    refinery: RefineryScope
    access: AccessGrant
    scope_kind: ScopeKind
    scope_id: str
    human_approved: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    ok: bool
    data: Any
    effect: ToolEffect
    provenance: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[[ToolContext, dict[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class _RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    """Validated execution boundary between agent reasoning and application actions."""

    def __init__(self) -> None:
        self._tools: dict[str, _RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        key = definition.name.strip()
        if not key:
            raise ToolExecutionError("Tool name is required")
        if key in self._tools:
            raise ToolExecutionError(f"Tool already registered: {key}")
        self._tools[key] = _RegisteredTool(definition, handler)

    def definitions(self) -> list[dict[str, Any]]:
        return [self._tools[name].definition.to_dict() for name in sorted(self._tools)]

    def get_definition(self, name: str) -> ToolDefinition | None:
        registered = self._tools.get(name)
        return registered.definition if registered else None

    @staticmethod
    def _validate_arguments(definition: ToolDefinition, arguments: dict[str, Any]) -> None:
        allowed = {parameter.name for parameter in definition.parameters}
        unknown = sorted(set(arguments) - allowed)
        if unknown:
            raise ToolExecutionError(
                f"Unknown argument(s) for {definition.name}: {', '.join(unknown)}"
            )
        missing = [
            parameter.name
            for parameter in definition.parameters
            if parameter.required and parameter.name not in arguments
        ]
        if missing:
            raise ToolExecutionError(
                f"Missing required argument(s) for {definition.name}: {', '.join(missing)}"
            )

    @staticmethod
    def _authorize(definition: ToolDefinition, context: ToolContext) -> None:
        if not context.access.permits_domain(definition.domain):
            raise ToolExecutionError(
                f"Actor {context.actor_id} is not authorized for {definition.domain.value} data"
            )
        if definition.requires_scope and not context.access.permits_scope(
            context.refinery,
            scope_kind=context.scope_kind,
            scope_id=context.scope_id,
        ):
            raise ToolExecutionError(
                f"Actor {context.actor_id} is not authorized for {context.scope_kind.value} scope {context.scope_id}"
            )

        # Human approval is deliberately not represented as an agent-callable tool.
        # This flag is reserved for future externally verified approval gates.
        if definition.effect == ToolEffect.CONTROLLED_DOCUMENT_PROPOSAL:
            return

    async def execute(
        self,
        name: str,
        *,
        context: ToolContext,
        arguments: dict[str, Any],
    ) -> ToolResult:
        registered = self._tools.get(name)
        if registered is None:
            raise ToolExecutionError(f"Unknown tool: {name}")

        self._validate_arguments(registered.definition, arguments)
        self._authorize(registered.definition, context)

        try:
            value = registered.handler(context, dict(arguments))
            if inspect.isawaitable(value):
                value = await value
        except ToolExecutionError:
            raise
        except Exception as exc:
            raise ToolExecutionError(f"{name} failed: {exc}") from exc

        return ToolResult(
            tool_name=name,
            ok=True,
            data=value,
            effect=registered.definition.effect,
            provenance={
                "actor_id": context.actor_id,
                "domain": registered.definition.domain.value,
                "scope_kind": context.scope_kind.value,
                "scope_id": context.scope_id,
            },
        )
