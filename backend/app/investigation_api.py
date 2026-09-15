"""FastAPI router for refinery-wide autonomous engineering investigations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .agent_tools import ToolContext
from .dynamic_investigation import DynamicInvestigator
from .refinery_model import AccessGrant, RefineryScope, UnitScope, default_engineering_domains
from .refinery_tools import build_refinery_tool_registry

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class InvestigationRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)
    user_id: str = Field(default="local-engineer", min_length=1, max_length=200)


def _local_context(user_id: str, unit_key: str) -> ToolContext:
    # Phase-1 local identity adapter. Enterprise identity/RBAC will replace this
    # adapter; authorization is still enforced by ToolRegistry, not by the LLM.
    unit = unit_key.strip().casefold()
    refinery = RefineryScope(id="local-refinery", name="Local Refinery", standalone_units=(UnitScope(id=unit, name=unit.upper()),))
    grant = AccessGrant(domains=default_engineering_domains(), refinery_ids=frozenset({refinery.id}))
    return ToolContext(actor_id=user_id, refinery=refinery, grant=grant, unit_id=unit)


@router.post("/run")
async def run_investigation(request: InvestigationRequest) -> dict[str, object]:
    try:
        registry = build_refinery_tool_registry()
        context = _local_context(request.user_id, request.unit_key)
        result = await DynamicInvestigator(registry).investigate(
            goal=request.goal, unit_key=request.unit_key, context=context
        )
        return {
            "mode": "local",
            "read_only_process_access": True,
            "goal": request.goal,
            "unit_key": request.unit_key.casefold(),
            "discovery": result.discovery,
            "analysis": result.analysis,
            "synthesis": result.synthesis,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
