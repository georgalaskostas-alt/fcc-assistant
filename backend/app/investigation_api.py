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
from .investigation_store import EvidenceRecord, InvestigationStore
from .investigation_service import InvestigationService
from .investigation_continuation import continue_saved_investigation
from .refinery_model import AccessGrant, RefineryScope, ScopeKind, UnitScope, default_engineering_domains
from .refinery_tools import build_refinery_tool_registry

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


class InvestigationContinueRequest(BaseModel):
    utterance: str = Field(min_length=2, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)
    investigation_id: str | None = Field(default=None, min_length=4, max_length=120)


class InvestigationPreviousContext(BaseModel):
    resolved_tags: list[str] = Field(default_factory=list, max_length=12)
    time_window: dict[str, str] | None = None


class InvestigationRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    unit_key: str = Field(min_length=1, max_length=80)
    previous_context: InvestigationPreviousContext | None = None



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
            candidates = [row]
            tag = row.get("tag")
            if isinstance(tag, dict):
                candidates.append(tag)
            metadata = row.get("metadata")
            if isinstance(metadata, dict):
                candidates.append(metadata)
            for candidate in candidates:
                for key in ("engineering_unit", "unit_of_measure", "uom", "unit", "units"):
                    value = candidate.get(key)
                    if value:
                        allowed.add(str(value).casefold())
    return allowed


@router.post("/run")
async def run_investigation(request: InvestigationRequest) -> dict[str, object]:
    try:
        tag_service, source = investigation_tag_service()
        registry = build_refinery_tool_registry(tag_service=tag_service)
        identity = active_identity()
        context = _local_context(identity, request.unit_key)
        previous_context = (
            request.previous_context.model_dump()
            if request.previous_context
            else None
        )
        result = await DynamicInvestigator(registry).investigate(
            goal=request.goal,
            unit_key=request.unit_key,
            context=context,
            previous_context=previous_context,
        )

        time_window = result.synthesis.get("time_window") if isinstance(result.synthesis, dict) else None
        build = runtime_build_identity()
        append_trace("investigation.window_resolved", {
            "goal": request.goal,
            "unit_key": request.unit_key.casefold(),
            "time_window": time_window,
            "backend_build": build,
        })

        reasoning = await reason_about_investigation(goal=request.goal, synthesis=result.synthesis, data_source=source)

        # Every initial run is durable.  The dynamic investigator owns the rich
        # evidence workflow, while the service/store own persistence and resume.
        # Persist the governed evidence package and checkpoint the exact context
        # needed by /saved and /continue.
        store = InvestigationStore()
        saved = store.create(
            goal=request.goal,
            user_id=identity.actor_id,
            unit_key=request.unit_key,
        )
        seen_source_ids: set[str] = set()
        for evidence in result.synthesis.get("evidence_package", []):
            if not isinstance(evidence, dict):
                continue
            source_id = str(
                evidence.get("stable_evidence_id")
                or evidence.get("evidence_id")
                or ""
            ).strip()
            if not source_id or source_id in seen_source_ids:
                continue
            payload = evidence.get("data") if isinstance(evidence.get("data"), dict) else {}
            provenance = evidence.get("provenance") if isinstance(evidence.get("provenance"), dict) else {}
            store.add_evidence(
                saved.id,
                EvidenceRecord(
                    source_type=str(evidence.get("tool") or "tool"),
                    source_id=source_id,
                    summary=str(evidence.get("description") or evidence.get("tool") or "Investigation evidence"),
                    provenance=provenance,
                    payload=payload,
                ),
            )
            seen_source_ids.add(source_id)
        service = InvestigationService(registry=registry, store=store)
        saved = service.checkpoint(
            saved.id,
            trail=reasoning.get("investigation_trail")
            if isinstance(reasoning.get("investigation_trail"), dict)
            else {},
            synthesis=result.synthesis,
        )

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
            "investigation": saved.to_dict(),
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
        context = _local_context(identity, request.unit_key)
        store = InvestigationStore()
        if request.investigation_id:
            item = store.get(request.investigation_id)
            if item is None:
                raise ValueError("Unknown investigation")
            result = await continue_saved_investigation(
                registry=registry,
                store=store,
                investigation_id=request.investigation_id,
                context=context,
                data_source=source,
            )
            return {
                "mode":"local",
                "data_source":source,
                "read_only_process_access":True,
                "status":"continued",
                **result,
            }
        service = InvestigationService(registry=registry, store=store)
        result = await service.continue_from_conversation(
            user_id=identity.actor_id, utterance=request.utterance, context=context,
            data_source=source, unit_key=request.unit_key)
        return {"mode":"local","data_source":source,"read_only_process_access":True,**result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
