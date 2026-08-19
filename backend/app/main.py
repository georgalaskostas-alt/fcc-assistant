from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .analytics import AnalyticsError, compare_summaries, summarize_pi_payload
from .local_ai import LocalAIClient, LocalAIError
from .pi_client import PIWebAPIClient, PIWebAPIError
from .settings import get_settings
from .shift_report import ShiftReportEngine, ShiftReportError
from .tag_registry import TagRegistry, TagRegistryError
from .tag_service import TagService, TagServiceError

app = FastAPI(
    title="FCC Assistant Local API",
    version="0.1.0",
    description="Local backend for FCC process analysis and reporting.",
)


class AIAnalysisRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    evidence: dict[str, object] = Field(default_factory=dict)


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


def raise_tag_service_error(exc: TagServiceError) -> None:
    message = str(exc)
    status = 404 if message.startswith("Unknown tag key") else 502
    raise HTTPException(status_code=status, detail=message) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fcc-assistant-backend", "mode": "local"}


@app.get("/api/v1/system/capabilities")
def capabilities() -> dict[str, object]:
    settings = get_settings()
    return {
        "pi_web_api": "configured" if settings.pi_web_api_url else "not_configured",
        "local_ai": "configured" if settings.local_ai_model else "not_configured",
        "plant_write_access": False,
        "features": [
            "pi-read-only", "tag-registry", "named-tag-data",
            "engineering-analytics", "period-comparison", "shift-reports",
            "local-ai-assistant",
        ],
    }


@app.get("/api/v1/ai/status")
async def ai_status() -> dict[str, object]:
    try:
        return await LocalAIClient().status()
    except LocalAIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/ai/analyze")
async def ai_analyze(request: AIAnalysisRequest) -> dict[str, object]:
    if not request.evidence:
        raise HTTPException(
            status_code=422,
            detail="Local AI analysis requires structured process evidence",
        )
    try:
        response = await LocalAIClient().generate(request.question, request.evidence)
    except LocalAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "mode": "local",
        "read_only": True,
        "model": response.model,
        "answer": response.text,
    }


@app.get("/api/v1/tags")
def list_tags(q: str | None = Query(default=None)) -> dict[str, object]:
    registry = get_tag_registry()
    tags = registry.find(q) if q is not None else registry.list()
    return {"count": len(tags), "items": [asdict(tag) for tag in tags]}


@app.get("/api/v1/tags/{key}")
def get_tag(key: str) -> dict[str, object]:
    tag = get_tag_registry().get(key)
    if tag is None:
        raise HTTPException(status_code=404, detail=f"Unknown FCC tag key: {key}")
    return asdict(tag)


@app.get("/api/v1/tags/{key}/value")
async def tag_current_value(key: str) -> dict[str, object]:
    try:
        return await get_tag_service().current_value(key)
    except TagServiceError as exc:
        raise_tag_service_error(exc)


@app.get("/api/v1/tags/{key}/recorded")
async def tag_recorded_values(key: str, start_time: str = Query(..., alias="startTime"), end_time: str = Query(..., alias="endTime"), max_count: int = Query(1000, alias="maxCount", ge=1, le=10000)) -> dict[str, object]:
    try:
        return await get_tag_service().recorded_values(key, start_time, end_time, max_count)
    except TagServiceError as exc:
        raise_tag_service_error(exc)


@app.get("/api/v1/tags/{key}/summary")
async def tag_summary(key: str, start_time: str = Query(..., alias="startTime"), end_time: str = Query(..., alias="endTime"), max_count: int = Query(1000, alias="maxCount", ge=2, le=10000)) -> dict[str, object]:
    try:
        payload = await get_tag_service().recorded_values(key, start_time, end_time, max_count)
        summary = summarize_pi_payload(payload["data"])
    except TagServiceError as exc:
        raise_tag_service_error(exc)
    except (AnalyticsError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tag": key, "startTime": start_time, "endTime": end_time, "summary": asdict(summary)}


@app.get("/api/v1/tags/{key}/compare")
async def compare_tag_periods(key: str, current_start: str = Query(..., alias="currentStart"), current_end: str = Query(..., alias="currentEnd"), reference_start: str = Query(..., alias="referenceStart"), reference_end: str = Query(..., alias="referenceEnd"), max_count: int = Query(1000, alias="maxCount", ge=2, le=10000)) -> dict[str, object]:
    service = get_tag_service()
    try:
        current_payload = await service.recorded_values(key, current_start, current_end, max_count)
        reference_payload = await service.recorded_values(key, reference_start, reference_end, max_count)
        current_summary = summarize_pi_payload(current_payload["data"])
        reference_summary = summarize_pi_payload(reference_payload["data"])
        comparison = compare_summaries(current_summary, reference_summary)
    except TagServiceError as exc:
        raise_tag_service_error(exc)
    except (AnalyticsError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"tag": key, "current": asdict(current_summary), "reference": asdict(reference_summary), "comparison": asdict(comparison)}


@app.get("/api/v1/reports/shift")
async def shift_report(start_time: str = Query(..., alias="startTime"), end_time: str = Query(..., alias="endTime"), tags: str | None = Query(default=None), max_count: int = Query(1000, alias="maxCount", ge=2, le=10000)) -> dict[str, object]:
    tag_keys = [item.strip() for item in tags.split(",") if item.strip()] if tags else None
    try:
        return await ShiftReportEngine(get_tag_service()).generate(start_time, end_time, tag_keys, max_count)
    except ShiftReportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/pi/status")
async def pi_status() -> dict[str, object]:
    client = PIWebAPIClient()
    try:
        payload = await client.root()
    except PIWebAPIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"connected": True, "read_only": True, "pi_web_api": payload}


@app.get("/api/v1/pi/streams/{web_id}/value")
async def pi_current_value(web_id: str) -> dict[str, object]:
    try:
        return await PIWebAPIClient().current_value(web_id)
    except PIWebAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/pi/streams/{web_id}/recorded")
async def pi_recorded_values(web_id: str, start_time: str = Query(..., alias="startTime"), end_time: str = Query(..., alias="endTime"), max_count: int = Query(1000, alias="maxCount", ge=1, le=10000)) -> dict[str, object]:
    try:
        return await PIWebAPIClient().recorded_values(web_id, start_time, end_time, max_count)
    except PIWebAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
