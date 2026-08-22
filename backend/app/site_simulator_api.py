from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from .simulator import SimulatedSiteSource

router = APIRouter(prefix="/api/v1/site-simulator", tags=["site-simulator"])


@router.get("/tags")
def site_simulator_tags() -> dict[str, object]:
    try:
        items = SimulatedSiteSource().list_tags()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "simulated", "scope": "site", "count": len(items), "items": items}


@router.get("/recorded/{key}")
def site_simulator_recorded(
    key: str,
    start_time: datetime = Query(..., alias="startTime"),
    end_time: datetime = Query(..., alias="endTime"),
    step_minutes: int = Query(15, alias="stepMinutes", ge=1, le=60),
) -> dict[str, object]:
    try:
        data = SimulatedSiteSource().recorded_values(key, start_time, end_time, step_minutes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown simulated site tag: {key}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"mode": "simulated", "scope": "site", "tag": key, "data": data}


@router.get("/demo-shift")
def site_simulator_demo_shift() -> dict[str, object]:
    try:
        data = SimulatedSiteSource().demo_shift()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "simulated", "scope": "site", "read_only": True, "data": data}
