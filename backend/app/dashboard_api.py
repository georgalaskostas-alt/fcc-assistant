from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .dashboard_config import DashboardCommandError, plan_dashboard_command
from .dashboard_store import DashboardStore
from .site_model import default_site_model

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class DashboardCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    workspace: str = Field(default="default", min_length=1, max_length=120)


class DashboardSaveRequest(BaseModel):
    title: str = Field(default="Operations Overview", min_length=1, max_length=200)
    widgets: list[dict[str, object]] = Field(default_factory=list)


@router.get("/site")
def dashboard_site() -> dict[str, object]:
    site = default_site_model()
    return {"name": site.name, "units": site.list_units(), "read_only": True}


@router.get("/workspaces/{workspace}")
def dashboard_workspace(workspace: str) -> dict[str, object]:
    return DashboardStore().get(workspace)


@router.put("/workspaces/{workspace}")
def dashboard_workspace_save(workspace: str, request: DashboardSaveRequest) -> dict[str, object]:
    return DashboardStore().put(workspace, request.model_dump())


@router.post("/command")
def dashboard_command(request: DashboardCommandRequest) -> dict[str, object]:
    store = DashboardStore()
    current = store.get(request.workspace)
    current_widgets = current.get("widgets")
    if not isinstance(current_widgets, list):
        current_widgets = []

    try:
        plan = plan_dashboard_command(request.command, default_site_model(), current_widgets=current_widgets)
    except DashboardCommandError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workspace = store.apply_plan(request.workspace, plan)
    return {"plan": plan, "workspace": workspace}
