from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query

from .pi_client import PIWebAPIClient, PIWebAPIError
from .settings import get_settings
from .tag_registry import TagRegistry, TagRegistryError
from .tag_service import TagService, TagServiceError

app = FastAPI(
    title="FCC Assistant Local API",
    version="0.1.0",
    description="Local backend for FCC process analysis and reporting.",
)


def get_tag_registry() -> TagRegistry:
    settings = get_settings()
    try:
        return TagRegistry(settings.tag_config_path)
    except TagRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def get_tag_service() -> TagService:
    try:
        return TagService()
    except (TagRegistryError, TagServiceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "fcc-assistant-backend",
        "mode": "local",
    }


@app.get("/api/v1/system/capabilities")
def capabilities() -> dict[str, object]:
    settings = get_settings()
    return {
        "pi_web_api": "configured" if settings.pi_web_api_url else "not_configured",
        "local_ai": "not_configured",
        "plant_write_access": False,
        "features": [
            "pi-read-only",
            "tag-registry",
            "named-tag-data",
            "engineering-analytics",
            "shift-reports",
            "local-ai-assistant",
        ],
    }


@app.get("/api/v1/tags")
def list_tags(q: str | None = Query(default=None)) -> dict[str, object]:
    registry = get_tag_registry()
    tags = registry.find(q) if q is not None else registry.list()
    return {
        "count": len(tags),
        "items": [asdict(tag) for tag in tags],
    }


@app.get("/api/v1/tags/{key}")
def get_tag(key: str) -> dict[str, object]:
    registry = get_tag_registry()
    tag = registry.get(key)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Unknown FCC tag key: {key}")
    return asdict(tag)


@app.get("/api/v1/tags/{key}/value")
async def tag_current_value(key: str) -> dict[str, object]:
    service = get_tag_service()
    try:
        return await service.current_value(key)
    except TagServiceError as exc:
        message = str(exc)
        status = 404 if message.startswith("Unknown tag key") else 502
        raise HTTPException(status_code=status, detail=message) from exc


@app.get("/api/v1/tags/{key}/recorded")
async def tag_recorded_values(
    key: str,
    start_time: str = Query(..., alias="startTime"),
    end_time: str = Query(..., alias="endTime"),
    max_count: int = Query(1000, alias="maxCount", ge=1, le=10000),
) -> dict[str, object]:
    service = get_tag_service()
    try:
        return await service.recorded_values(
            key=key,
            start_time=start_time,
            end_time=end_time,
            max_count=max_count,
        )
    except TagServiceError as exc:
        message = str(exc)
        status = 404 if message.startswith("Unknown tag key") else 502
        raise HTTPException(status_code=status, detail=message) from exc


@app.get("/api/v1/pi/status")
async def pi_status() -> dict[str, object]:
    client = PIWebAPIClient()
    try:
        payload = await client.root()
    except PIWebAPIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "connected": True,
        "read_only": True,
        "pi_web_api": payload,
    }


@app.get("/api/v1/pi/streams/{web_id}/value")
async def pi_current_value(web_id: str) -> dict[str, object]:
    client = PIWebAPIClient()
    try:
        return await client.current_value(web_id)
    except PIWebAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/pi/streams/{web_id}/recorded")
async def pi_recorded_values(
    web_id: str,
    start_time: str = Query(..., alias="startTime"),
    end_time: str = Query(..., alias="endTime"),
    max_count: int = Query(1000, alias="maxCount", ge=1, le=10000),
) -> dict[str, object]:
    client = PIWebAPIClient()
    try:
        return await client.recorded_values(
            web_id=web_id,
            start_time=start_time,
            end_time=end_time,
            max_count=max_count,
        )
    except PIWebAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
