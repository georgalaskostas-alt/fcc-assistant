"""FastAPI router for refinery-wide autonomous engineering investigations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .agent_tools import ToolContext
from .dynamic_investigation import DynamicInvestigator
from .investigation_data_source import investigation_tag_service
from .refinery_model import AccessGrant, RefineryScope, ScopeKind, UnitScope, default_engineering_domains
from .refinery_tools import build_refinery_tool_registry

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class InvestigationRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)
    user_id: str = Field(default="local-engineer", min_length=1, max_length=200)


def _local_context(user_id: str, unit_key: str) -> ToolContext:
    """Phase-1 local identity adapter using the canonical ToolContext contract."""
    unit = unit_key.strip().casefold()
    refinery = RefineryScope(
        id="local-refinery",
        name="Local Refinery",
        standalone_units=(UnitScope(id=unit, name=unit.upper()),),
    )
    # Scope the development identity to the selected unit. This keeps the same
    # server-side authorization path that enterprise RBAC will use later.
    access = AccessGrant(
        domains=default_engineering_domains(),
        unit_ids=frozenset({unit}),
    )
    return ToolContext(
        actor_id=user_id,
        refinery=refinery,
        access=access,
        scope_kind=ScopeKind.UNIT,
        scope_id=unit,
        metadata={"identity_adapter": "phase1-local"},
    )


@router.post("/run")
async def run_investigation(request: InvestigationRequest) -> dict[str, object]:
    try:
        tag_service, source = investigation_tag_service()
        registry = build_refinery_tool_registry(tag_service=tag_service)
        context = _local_context(request.user_id, request.unit_key)
        result = await DynamicInvestigator(registry).investigate(
            goal=request.goal,
            unit_key=request.unit_key,
            context=context,
        )
        return {
            "mode": "local",
            "data_source": source,
            "read_only_process_access": True,
            "goal": request.goal,
            "unit_key": request.unit_key.casefold(),
            "discovery": result.discovery,
            "analysis": result.analysis,
            "synthesis": result.synthesis,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
