from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .dashboard_agent import plan_with_local_agent
from .dashboard_config import DashboardCommandError, plan_dashboard_command
from .dashboard_dialogue import DashboardDialogueStore, contextual_plan, resolve_units
from .dashboard_pending import DashboardPendingStore
from .dashboard_store import DashboardStore
from .diagnostic_trace import append_trace, clear_trace, recent_trace
from .site_model import load_site_model, site_runtime_status

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class DashboardCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    workspace: str = Field(default="default", min_length=1, max_length=120)


class DashboardSaveRequest(BaseModel):
    title: str = Field(default="Operations Overview", min_length=1, max_length=200)
    widgets: list[dict[str, object]] = Field(default_factory=list)


@router.get("/site")
def dashboard_site() -> dict[str, object]:
    site = load_site_model()
    return {"name": site.name, "units": site.list_units(), "read_only": True}


@router.get("/site/status")
def dashboard_site_status() -> dict[str, object]:
    return site_runtime_status()


@router.get("/diagnostics")
def dashboard_diagnostics(limit: int = 30) -> dict[str, object]:
    return {"local_only": True, "events": recent_trace(limit)}


@router.delete("/diagnostics")
def dashboard_diagnostics_clear() -> dict[str, object]:
    clear_trace()
    return {"cleared": True, "local_only": True}


@router.get("/workspaces/{workspace}")
def dashboard_workspace(workspace: str) -> dict[str, object]:
    return DashboardStore().get(workspace)


@router.put("/workspaces/{workspace}")
def dashboard_workspace_save(workspace: str, request: DashboardSaveRequest) -> dict[str, object]:
    return DashboardStore().put(workspace, request.model_dump())


def _steps(plan: dict[str, object]) -> list[dict[str, object]]:
    if str(plan.get("action", "")) != "transaction":
        return [plan]
    raw = plan.get("steps")
    return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []


def _planned_unit_keys(plan: dict[str, object]) -> set[str]:
    keys: set[str] = set()
    for step in _steps(plan):
        if str(step.get("action", "")) in {"answer", "clarify", "remove_widget", "remove_widgets", "resize_widget", "move_between"}:
            continue
        candidates: list[dict[str, object]] = []
        if isinstance(step.get("widget"), dict):
            candidates.append(step["widget"])  # type: ignore[arg-type]
        if isinstance(step.get("widgets"), list):
            candidates.extend(x for x in step["widgets"] if isinstance(x, dict))  # type: ignore[index]
        keys.update(str(x.get("unit_key", "")).casefold() for x in candidates if x.get("unit_key"))
    return keys


def _validate_unit_intent(command: str, site, aliases: dict[str, str], plan: dict[str, object]) -> None:
    requested = {u.key.casefold() for u in resolve_units(command, site, aliases)}
    planned = _planned_unit_keys(plan)
    if requested and planned and not planned.issubset(requested):
        raise DashboardCommandError("Κατάλαβα διαφορετική μονάδα από αυτή που ζήτησες. Δεν άλλαξα τίποτα.")


def _validate_transaction(plan: dict[str, object]) -> list[dict[str, object]]:
    steps = _steps(plan)
    allowed = {"add_widget", "add_widgets", "remove_widget", "remove_widgets", "replace_widget", "resize_widget", "move_between", "answer"}
    if not steps or any(str(step.get("action", "")) not in allowed for step in steps):
        raise DashboardCommandError("Δεν μπόρεσα να επαληθεύσω με ασφάλεια όλη τη σύνθετη εντολή. Δεν άλλαξα τίποτα.")
    return steps


def _legacy_plan(command: str, site, state: dict[str, object], widgets: list[dict[str, object]], aliases: dict[str, str]) -> tuple[dict[str, object], str | None]:
    plan, message = contextual_plan(command, site, state, widgets, learned_aliases=aliases)
    if plan is not None:
        return plan, message
    resolved = resolve_units(command, site, aliases)
    working = f"{command} {' '.join(u.key for u in resolved)}" if resolved else command
    return plan_dashboard_command(working, site, current_widgets=widgets), None


@router.post("/command")
async def dashboard_command(request: DashboardCommandRequest) -> dict[str, object]:
    store = DashboardStore()
    dialogue = DashboardDialogueStore()
    pending_store = DashboardPendingStore()
    current = store.get(request.workspace)
    raw = current.get("widgets")
    widgets = [dict(x) for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []
    agent_result = None
    route = "unknown"

    try:
        site = load_site_model()
        aliases = dialogue.aliases()
        explicit = resolve_units(request.command, site, aliases)
        pending = pending_store.get(request.workspace)
        append_trace(
            "command.received",
            {
                "command": request.command,
                "workspace": request.workspace,
                "explicit_units": [u.key for u in explicit],
                "pending_intent": pending,
                "widgets_before": [
                    {"id": w.get("id"), "unit_key": w.get("unit_key"), "tag_keys": w.get("tag_keys"), "type": w.get("type")}
                    for w in widgets
                ],
            },
        )
        if len(explicit) == 1:
            dialogue.remember_requested_unit(request.workspace, explicit[0].key)
        state = dialogue.get_state(request.workspace)
        if pending is not None:
            state["pending_intent"] = pending

        agent_result = await plan_with_local_agent(request.command, site, state, widgets)
        if agent_result is not None:
            plan, message = agent_result.plan, agent_result.message
            route = "local-llm"
        else:
            plan, message = _legacy_plan(request.command, site, state, widgets, aliases)
            route = "deterministic-fallback"

        _validate_unit_intent(request.command, site, aliases, plan)
        steps = _validate_transaction(plan) if str(plan.get("action", "")) == "transaction" else []
    except DashboardCommandError as exc:
        message = str(exc)
        plan = {"action": "clarify", "read_only": True, "requires_confirmation": False, "needs_clarification": True}
        dialogue.remember(request.workspace, request.command, plan, current, message, previous_widgets=widgets)
        append_trace("command.rejected", {"command": request.command, "route": route, "message": message, "pending_intent": pending_store.get(request.workspace)})
        return {"plan": plan, "workspace": current, "message": message, "needs_clarification": True, "agent": route, "site": site_runtime_status()}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    action = str(plan.get("action", ""))
    if action == "clarify":
        frame = plan.get("pending_intent")
        if isinstance(frame, dict):
            pending_store.set(request.workspace, frame)
            append_trace("command.pending", {"workspace": request.workspace, "pending_intent": frame})
        workspace = current
    else:
        workspace = store.apply_transaction(request.workspace, steps) if action == "transaction" else store.apply_plan(request.workspace, plan)
        if action not in {"answer"}:
            pending_store.clear(request.workspace)

    append_trace(
        "command.executed",
        {
            "command": request.command,
            "route": route,
            "plan": plan,
            "message": message,
            "pending_after": pending_store.get(request.workspace),
            "widgets_after": [
                {"id": w.get("id"), "unit_key": w.get("unit_key"), "tag_keys": w.get("tag_keys"), "type": w.get("type")}
                for w in (workspace.get("widgets") or [])
                if isinstance(w, dict)
            ],
        },
    )
    dialogue.remember(request.workspace, request.command, plan, workspace, message, previous_widgets=widgets)
    return {
        "plan": plan,
        "workspace": workspace,
        "message": message,
        "needs_clarification": bool(plan.get("needs_clarification", False)),
        "agent": route,
        "pending_intent": pending_store.get(request.workspace),
        "site": site_runtime_status(),
    }
