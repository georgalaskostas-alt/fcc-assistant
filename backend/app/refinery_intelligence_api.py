from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .engineering_context import EngineeringContextBuilder
from .learned_patterns import LearnedPatternStore
from .local_ai import LocalAIClient, LocalAIError
from .operational_episode import OperationalEpisodeStore, outcome_envelope
from .production_domain import ProductionStore

router = APIRouter(prefix="/api/v1/intelligence", tags=["refinery-intelligence"])


class EpisodeCreateRequest(BaseModel):
    unit_key: str = Field(min_length=1, max_length=120)
    start_time: str
    end_time: str
    kind: str = "stable"
    regime: str = Field(min_length=1, max_length=300)
    configuration_version: str = "current"
    inputs: dict[str, float | str] = Field(default_factory=dict)
    operating_state: dict[str, float | str] = Field(default_factory=dict)
    constraints: dict[str, float | str] = Field(default_factory=dict)
    outputs: dict[str, float | str] = Field(default_factory=dict)
    quality: dict[str, float | str] = Field(default_factory=dict)
    outcomes: dict[str, float | str] = Field(default_factory=dict)
    source: str = "process_history"


class SimilarEpisodesRequest(BaseModel):
    unit_key: str = Field(min_length=1, max_length=120)
    configuration_version: str = "current"
    context: dict[str, float | str] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)


class ProductionCreateRequest(BaseModel):
    scope_kind: str
    scope_id: str = Field(min_length=1, max_length=120)
    period_start: str
    period_end: str
    metric: str = Field(min_length=1, max_length=200)
    actual: float
    plan: float
    unit: str = Field(default="", max_length=80)
    source: str = "manual_or_connector"


class PatternCreateRequest(BaseModel):
    unit_key: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=4000)
    context: dict[str, float | str] = Field(default_factory=dict)
    outcome: dict[str, float | str] = Field(default_factory=dict)
    comparable_episodes: int = Field(ge=2)
    confidence: float = Field(ge=0, le=1)


class PatternReviewRequest(BaseModel):
    status: str
    reviewed_by: str = Field(min_length=1, max_length=300)
    engineer_note: str = Field(default="", max_length=5000)


class EngineeringAnalyzeRequest(BaseModel):
    unit_key: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=4000)
    at_time: str | None = None
    configuration_version: str | None = None
    process_evidence: dict[str, object] = Field(default_factory=dict)
    comparison_context: dict[str, float | str] = Field(default_factory=dict)


@router.post("/episodes")
def create_episode(request: EpisodeCreateRequest) -> dict[str, object]:
    try:
        episode = OperationalEpisodeStore().add(**request.model_dump())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"episode": asdict(episode), "read_only": True}


@router.get("/episodes/{unit_key}")
def list_episodes(
    unit_key: str,
    configuration_version: str | None = Query(default=None, alias="configurationVersion"),
) -> dict[str, object]:
    episodes = OperationalEpisodeStore().list(unit_key=unit_key, configuration_version=configuration_version)
    return {
        "unit_key": unit_key,
        "count": len(episodes),
        "episodes": [asdict(episode) for episode in episodes],
        "outcome_envelope": outcome_envelope(episodes),
        "read_only": True,
    }


@router.post("/episodes/similar")
def similar_episodes(request: SimilarEpisodesRequest) -> dict[str, object]:
    items = OperationalEpisodeStore().similar(
        unit_key=request.unit_key,
        context=request.context,
        configuration_version=request.configuration_version,
        limit=request.limit,
    )
    return {
        "unit_key": request.unit_key,
        "configuration_version": request.configuration_version,
        "count": len(items),
        "matches": [
            {
                "episode": asdict(item.episode),
                "similarity": item.similarity,
                "matched_features": list(item.matched_features),
            }
            for item in items
        ],
        "read_only": True,
    }


@router.post("/patterns")
def add_pattern(request: PatternCreateRequest) -> dict[str, object]:
    try:
        pattern = LearnedPatternStore().add_candidate(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"pattern": asdict(pattern), "read_only": True}


@router.get("/patterns/{unit_key}")
def list_patterns(unit_key: str, status: str | None = None) -> dict[str, object]:
    if status not in {None, "candidate", "approved", "rejected"}:
        raise HTTPException(status_code=422, detail="invalid pattern status")
    items = LearnedPatternStore().list(unit_key=unit_key, status=status)  # type: ignore[arg-type]
    return {"unit_key": unit_key, "count": len(items), "patterns": [asdict(item) for item in items], "read_only": True}


@router.post("/patterns/{pattern_id}/review")
def review_pattern(pattern_id: str, request: PatternReviewRequest) -> dict[str, object]:
    if request.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="status must be approved or rejected")
    try:
        pattern = LearnedPatternStore().review(
            pattern_id,
            status=request.status,  # type: ignore[arg-type]
            reviewed_by=request.reviewed_by,
            engineer_note=request.engineer_note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="pattern not found") from exc
    return {"pattern": asdict(pattern), "read_only": True}


@router.post("/production")
def add_production(request: ProductionCreateRequest) -> dict[str, object]:
    try:
        record = ProductionStore().add(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = asdict(record)
    payload["variance"] = record.variance
    payload["attainment"] = record.attainment
    return {"record": payload, "read_only": True}


@router.get("/production/{scope_kind}/{scope_id}")
def production_summary(scope_kind: str, scope_id: str) -> dict[str, object]:
    if scope_kind not in {"refinery", "complex", "unit"}:
        raise HTTPException(status_code=422, detail="scope_kind must be refinery, complex or unit")
    return {**ProductionStore().summary(scope_kind=scope_kind, scope_id=scope_id), "read_only": True}


@router.get("/context/{unit_key}")
def engineering_context(
    unit_key: str,
    at_time: str | None = Query(default=None, alias="atTime"),
    configuration_version: str | None = Query(default=None, alias="configurationVersion"),
) -> dict[str, object]:
    return {
        **EngineeringContextBuilder().for_unit(
            unit_key,
            at_time=at_time,
            configuration_version=configuration_version,
        ),
        "read_only": True,
    }


@router.post("/analyze")
async def engineering_analyze(request: EngineeringAnalyzeRequest) -> dict[str, object]:
    context = EngineeringContextBuilder().for_unit(
        request.unit_key,
        at_time=request.at_time,
        configuration_version=request.configuration_version,
        comparison_context=request.comparison_context or None,
    )
    evidence = {
        "scope": {"kind": "unit", "unit_key": request.unit_key.casefold()},
        "process_evidence": request.process_evidence,
        "engineering_context": context,
        "policy": {
            "read_only": True,
            "external_process_ai": False,
            "do_not_invent_missing_values": True,
            "association_is_not_causation": True,
        },
    }
    try:
        response = await LocalAIClient().generate(request.question, evidence)
    except LocalAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "mode": "local",
        "scope": request.unit_key.casefold(),
        "model": response.model,
        "answer": response.text,
        "evidence_summary": {
            "knowledge_status": context["knowledge"].get("knowledge_status"),
            "historical_episode_count": context["historical_episode_count"],
            "approved_pattern_count": len(context["approved_learned_patterns"]),
            "comparable_episode_count": len(context["comparable_episodes"]),
        },
        "read_only": True,
    }
