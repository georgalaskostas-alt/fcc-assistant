from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from .simulator import SimulatedSiteSource

router = APIRouter(prefix="/api/v1/site-simulator", tags=["site-simulator"])

# Older FCC-only workspaces stored these tag keys before the multi-unit semantic
# catalog was introduced. Keep them readable while users migrate naturally to
# site-scoped widgets. These aliases are development-simulator only.
_LEGACY_FCC_KEYS = {
    "reaction_temperature": "reactor_temp",
    "regenerator_temperature": "regen_temp",
    "regenerator_o2": "regen_o2",
}


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
        source = SimulatedSiteSource()
        data = source.demo_shift()
        tags = source.list_tags()

        # Compatibility bridge for FCC-only widgets already persisted locally.
        # Only the first/FCC unit receives unscoped aliases, so aliases can never
        # make another process unit look like FCC data.
        first_unit = source.site.units[0].key if source.site.units else None
        for tag in tags:
            if tag.get("unit_key") != first_unit:
                continue
            key = str(tag.get("key") or "")
            semantic = str(tag.get("semantic_key") or "")
            if key not in data or not semantic:
                continue
            data.setdefault(semantic, data[key])
            legacy_key = _LEGACY_FCC_KEYS.get(semantic)
            if legacy_key:
                data.setdefault(legacy_key, data[key])
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"mode": "simulated", "scope": "site", "read_only": True, "data": data}
