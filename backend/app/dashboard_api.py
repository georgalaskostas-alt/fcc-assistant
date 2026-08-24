from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .dashboard_agent import plan_with_local_agent
from .dashboard_config import DashboardCommandError, plan_dashboard_command
from .dashboard_dialogue import DashboardDialogueStore, contextual_plan, resolve_units
from .dashboard_store import DashboardStore
from .site_model import load_site_model

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


@router.get("/workspaces/{workspace}")
def dashboard_workspace(workspace: str) -> dict[str, object]:
    return DashboardStore().get(workspace)


@router.put("/workspaces/{workspace}")
def dashboard_workspace_save(workspace: str, request: DashboardSaveRequest) -> dict[str, object]:
    return DashboardStore().put(workspace, request.model_dump())


def _planned_unit_keys(plan: dict[str, object]) -> set[str]:
    if str(plan.get("action", "")) in {"answer", "clarify", "remove_widget", "remove_widgets", "resize_widget", "move_between"}:
        return set()
    candidates: list[dict[str, object]] = []
    if isinstance(plan.get("widget"), dict):
        candidates.append(plan["widget"])  # type: ignore[arg-type]
    if isinstance(plan.get("widgets"), list):
        candidates.extend(item for item in plan["widgets"] if isinstance(item, dict))  # type: ignore[index]
    return {str(item.get("unit_key", "")).casefold() for item in candidates if item.get("unit_key")}


def _validate_unit_intent(command: str, site, aliases: dict[str, str], plan: dict[str, object]) -> None:
    requested = {unit.key.casefold() for unit in resolve_units(command, site, aliases)}
    planned = _planned_unit_keys(plan)
    if requested and planned and not planned.issubset(requested):
        raise DashboardCommandError(
            "Κατάλαβα διαφορετική μονάδα από αυτή που θα χρησιμοποιούσε η ενέργεια. "
            "Δεν άλλαξα τίποτα. Πες μου ποια μονάδα εννοείς."
        )


def _apply_bulk_remove(store: DashboardStore, workspace_name: str, current: dict[str, object], plan: dict[str, object]) -> dict[str, object]:
    raw_ids = plan.get("target_ids")
    target_ids = {str(value) for value in raw_ids} if isinstance(raw_ids, list) else set()
    raw_widgets = current.get("widgets")
    widgets = [dict(widget) for widget in raw_widgets if isinstance(widget, dict)] if isinstance(raw_widgets, list) else []
    remaining = [widget for widget in widgets if str(widget.get("id", "")) not in target_ids]
    for index, widget in enumerate(remaining):
        layout = widget.get("layout")
        if not isinstance(layout, dict):
            layout = {}
            widget["layout"] = layout
        layout["order"] = index
    return store.put(workspace_name, {**current, "widgets": remaining})


def _legacy_plan(command: str, site, state: dict[str, object], widgets: list[dict[str, object]], aliases: dict[str, str]) -> tuple[dict[str, object], str | None]:
    """Deterministic fallback only when the local LLM runtime is unavailable.

    It is deliberately not the primary natural-language path anymore.
    """
    plan, message = contextual_plan(command, site, state, widgets, learned_aliases=aliases)
    if plan is not None:
        return plan, message
    resolved = resolve_units(command, site, aliases)
    working = command
    if resolved:
        working = f"{command} {' '.join(unit.key for unit in resolved)}"
    return plan_dashboard_command(working, site, current_widgets=widgets), None


@router.post("/command")
async def dashboard_command(request: DashboardCommandRequest) -> dict[str, object]:
    store = DashboardStore()
    dialogue = DashboardDialogueStore()
    current = store.get(request.workspace)
    raw_widgets = current.get("widgets")
    current_widgets = [dict(item) for item in raw_widgets if isinstance(item, dict)] if isinstance(raw_widgets, list) else []

    try:
        site = load_site_model()
        aliases = dialogue.aliases()
        explicit_units = resolve_units(request.command, site, aliases)
        if len(explicit_units) == 1:
            dialogue.remember_requested_unit(request.workspace, explicit_units[0].key)
        state = dialogue.get_state(request.workspace)

        # PRIMARY PATH: a real local LLM interprets unrestricted natural language and
        # emits semantic intent. dashboard_agent then compiles it against the real local
        # unit/tag/widget catalog. The LLM never receives authority to invent executable ids.
        agent_result = await plan_with_local_agent(request.command, site, state, current_widgets)
        if agent_result is not None:
            plan, message = agent_result.plan, agent_result.message
        else:
            plan, message = _legacy_plan(request.command, site, state, current_widgets, aliases)

        # Hard deterministic guard after AI reasoning. An explicitly spoken unit can
        # never silently become another unit (e.g. Hydrocracker -> FCC).
        _validate_unit_intent(request.command, site, aliases, plan)

    except DashboardCommandError as exc:
        message = str(exc)
        plan = {"action": "clarify", "read_only": True, "requires_confirmation": False, "needs_clarification": True}
        dialogue.remember(request.workspace, request.command, plan, current, message)
        return {"plan": plan, "workspace": current, "message": message, "needs_clarification": True, "agent": "local-llm"}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    action = str(plan.get("action", ""))
    if action == "remove_widgets":
        workspace = _apply_bulk_remove(store, request.workspace, current, plan)
    elif action == "clarify":
        workspace = current
    else:
        workspace = store.apply_plan(request.workspace, plan)

    dialogue.remember(request.workspace, request.command, plan, workspace, message)
    return {
        "plan": plan,
        "workspace": workspace,
        "message": message,
        "needs_clarification": bool(plan.get("needs_clarification", False)),
        "agent": "local-llm" if agent_result is not None else "deterministic-fallback",
    }
