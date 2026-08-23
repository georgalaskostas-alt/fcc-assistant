from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .unit_knowledge import UnitKnowledgeError, UnitKnowledgeStore

router = APIRouter(prefix="/api/v1/knowledge", tags=["unit-knowledge"])


class ManualCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    revision: str = Field(default="", max_length=120)
    source_path: str = Field(default="", max_length=2000)
    summary: str = Field(default="", max_length=30000)
    document_date: str | None = None
    status: str = "draft"


class RevampCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10000)
    effective_from: str
    effective_to: str | None = None
    approved_by: str = Field(default="", max_length=300)
    status: str = "draft"


class OverrideCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    manual_value: str = Field(default="", max_length=500)
    current_value: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=5000)
    effective_from: str
    effective_to: str | None = None
    manual_reference: str = Field(default="", max_length=1000)
    approved_by: str = Field(default="", max_length=300)
    status: str = "draft"


class KnowledgeStatusRequest(BaseModel):
    status: str


def _store() -> UnitKnowledgeStore:
    return UnitKnowledgeStore()


def _bad_request(exc: (UnitKnowledgeError | ValueError)) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/units/{unit_key}")
def unit_knowledge(unit_key: str) -> dict[str, object]:
    try:
        return _store().get_unit(unit_key)
    except UnitKnowledgeError as exc:
        raise _bad_request(exc) from exc


@router.get("/units/{unit_key}/effective")
def effective_unit_knowledge(unit_key: str, at_time: str | None = Query(default=None, alias="atTime")) -> dict[str, object]:
    try:
        return _store().effective_context(unit_key, at_time)
    except (UnitKnowledgeError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.post("/units/{unit_key}/manuals")
def add_manual(unit_key: str, request: ManualCreateRequest) -> dict[str, object]:
    try:
        return _store().add_manual(unit_key, **request.model_dump())
    except UnitKnowledgeError as exc:
        raise _bad_request(exc) from exc


@router.post("/units/{unit_key}/revamps")
def add_revamp(unit_key: str, request: RevampCreateRequest) -> dict[str, object]:
    try:
        return _store().add_revamp(unit_key, **request.model_dump())
    except (UnitKnowledgeError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.post("/units/{unit_key}/overrides")
def add_override(unit_key: str, request: OverrideCreateRequest) -> dict[str, object]:
    try:
        return _store().add_override(unit_key, **request.model_dump())
    except (UnitKnowledgeError, ValueError) as exc:
        raise _bad_request(exc) from exc


@router.post("/units/{unit_key}/status")
def set_knowledge_status(unit_key: str, request: KnowledgeStatusRequest) -> dict[str, object]:
    try:
        return _store().set_knowledge_status(unit_key, request.status)
    except UnitKnowledgeError as exc:
        raise _bad_request(exc) from exc
