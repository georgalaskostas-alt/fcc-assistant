"""FastAPI router for refinery-wide autonomous engineering investigations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .agent_tools import ToolContext
from .active_identity import ActiveIdentity, active_identity
from .investigation_access import visible_investigations
from .build_identity import runtime_build_identity
from .diagnostic_trace import append_trace
from .dynamic_investigation import DynamicInvestigator
from .engineering_claim_guard import claims_only_text, validate_engineering_narrative
from .investigation_data_source import investigation_tag_service
from .investigation_reasoning import reason_about_investigation
from .investigation_store import InvestigationStore
from .investigation_service import InvestigationService
from .investigation_continuation import continue_saved_investigation
from .refinery_model import AccessGrant, RefineryScope, ScopeKind, UnitScope, default_engineering_domains
from .refinery_tools import build_refinery_tool_registry

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class InvestigationContinueRequest(BaseModel):
    utterance: str = Field(min_length=2, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)


class InvestigationRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)



def _local_context(identity: ActiveIdentity, unit_key: str) -> ToolContext:
    unit = unit_key.strip().casefold()
    if unit not in identity.unit_ids:
        raise PermissionError("Requested unit is not available in the active authorization context")
    units=tuple(UnitScope(id=value,name=value.upper()) for value in sorted(identity.unit_ids))
    refinery = RefineryScope(id="local-refinery", name="Local Refinery", standalone_units=units)
    access = AccessGrant(domains=default_engineering_domains(), unit_ids=identity.unit_ids)
    return ToolContext(actor_id=identity.actor_id, refinery=refinery, access=access,
                       scope_kind=ScopeKind.UNIT, scope_id=unit,
                       metadata={"identity_adapter": identity.source})

def _source_units(synthesis: dict[str, object]) -> set[str]:
    """Only explicitly retrieved engineering units may appear in generated prose."""
    allowed: set[str] = set()
    evidence = synthesis.get("discovery_evidence")
    if not isinstance(evidence, list): return allowed
    for item in evidence:
        if not isinstance(item, dict) or item.get("tool") != "search_tags": continue
        data = item.get("data")
        rows = data if isinstance(data, list) else data.get("hits", data.get("tags", [])) if isinstance(data, dict) else []
        if not isinstance(rows, list): continue
        for row in rows:
            if not isinstance(row, dict): continue
            for key in ("engineering_unit", "unit_of_measure", "uom"):
                value = row.get(key)
                if value: allowed.add(str(value).casefold())
    return allowed


@router.post("/run")
async def run_investigation(request: InvestigationRequest) -> dict[str, object]:
    try:
        tag_service, source = investigation_tag_service()
        registry = build_refinery_tool_registry(tag_service=tag_service)
        identity = active_identity()
        context = _local_context(identity, request.unit_key)
        result = await DynamicInvestigator(registry).investigate(goal=request.goal, unit_key=request.unit_key, context=context)

        time_window = result.synthesis.get("time_window") if isinstance(result.synthesis, dict) else None
        build = runtime_build_identity()
        append_trace("investigation.window_resolved", {
            "goal": request.goal,
            "unit_key": request.unit_key.casefold(),
            "time_window": time_window,
            "backend_build": build,
        })

        reasoning = await reason_about_investigation(goal=request.goal, synthesis=result.synthesis, data_source=source)

        # A prompt is not a safety boundary. Re-check the final generated text
        # against evidence actually returned by governed tools before display.
        final_validation = validate_engineering_narrative(str(reasoning.get("text") or ""), allowed_units=_source_units(result.synthesis))
        reasoning["final_validation"] = final_validation
        if not final_validation["valid"]:
            reasoning["available"] = False
            reasoning["text"] = claims_only_text(
                reasoning.get("claims", []) if isinstance(reasoning.get("claims"), list) else [],
                simulated=source.get("data_quality") == "SIMULATED",
            )

        return {
            "mode": "local",
            "backend_build": build,
            "data_source": source,
            "read_only_process_access": True,
            "goal": request.goal,
            "unit_key": request.unit_key.casefold(),
            "discovery": result.discovery,
            "analysis": result.analysis,
            "synthesis": result.synthesis,
            "reasoning": reasoning,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/saved")
def list_saved_investigations(unit_key: str) -> dict[str, object]:
    identity=active_identity()
    context=_local_context(identity,unit_key)
    items=visible_investigations(InvestigationStore().list(user_id=identity.actor_id),context)
    return {"count":len(items),"items":[item.to_dict() for item in items],"local_only":True,
            "identity_source":identity.source}

@router.post("/continue")
async def continue_investigation(request: InvestigationContinueRequest) -> dict[str, object]:
    try:
        tag_service, source = investigation_tag_service()
        registry = build_refinery_tool_registry(tag_service=tag_service)
        identity = active_identity()
        context = _local_context(identity.actor_id, request.unit_key)
        service = InvestigationService(registry=registry, store=InvestigationStore())
        result = await service.continue_from_conversation(
            user_id=identity.actor_id, utterance=request.utterance, context=context,
            data_source=source, unit_key=request.unit_key)
        return {"mode":"local","data_source":source,"read_only_process_access":True,**result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
