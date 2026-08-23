from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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
