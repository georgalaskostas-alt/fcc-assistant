from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


def _canonicalize_unit_references(command: str, site, aliases: dict[str, str]) -> str:
    resolved = resolve_units(command, site, aliases)
    canonical_keys = [unit.key for unit in resolved]
    folded = command.casefold()
    canonical_keys.extend(unit_key for alias, unit_key in aliases.items() if alias in folded)
    canonical_keys = list(dict.fromkeys(key.casefold() for key in canonical_keys if key))
    if not canonical_keys:
        return command
    return f"{command} {' '.join(canonical_keys)}"


def _planned_unit_keys(plan: dict[str, object]) -> set[str]:
    action = str(plan.get("action", ""))
    if action in {"answer", "clarify", "remove_widget", "remove_widgets", "resize_widget", "move_between"}:
        return set()
    candidates: list[dict[str, object]] = []
    widget = plan.get("widget")
    if isinstance(widget, dict):
        candidates.append(widget)
    widgets = plan.get("widgets")
    if isinstance(widgets, list):
        candidates.extend(item for item in widgets if isinstance(item, dict))
    return {str(item.get("unit_key", "")).casefold() for item in candidates if item.get("unit_key")}


def _validate_unit_intent(command: str, site, aliases: dict[str, str], plan: dict[str, object]) -> None:
    requested = {unit.key.casefold() for unit in resolve_units(command, site, aliases)}
    if not requested:
        return
    planned = _planned_unit_keys(plan)
    if planned and not planned.issubset(requested):
        raise DashboardCommandError(
            "Η μονάδα που κατάλαβα δεν συμφωνεί με τη μονάδα της ενέργειας. "
            "Δεν άλλαξα τίποτα. Πες μου ξανά ποια μονάδα εννοείς."
        )


def _bulk_remove_plan(command: str, site, aliases: dict[str, str], widgets: list[dict[str, object]]) -> tuple[dict[str, object] | None, str | None]:
    text = command.casefold()
    remove_intent = any(token in text for token in (
        "αφαίρε", "αφαιρε", "βγάλε", "βγαλε", "διέγρα", "διεγρα", "σβήσε", "σβησε", "remove", "delete", "clear",
    ))
    all_intent = any(token in text for token in (
        "όλα", "ολα", "όλες", "ολες", "όλους", "ολους", "all", "every",
    ))
    graph_intent = any(token in text for token in (
        "γράφημα", "γραφημα", "γραφήματα", "γραφηματα", "διάγραμμα", "διαγραμμα", "διαγράμματα", "διαγραμματα", "trend", "chart", "charts",
    ))
    if not (remove_intent and all_intent and graph_intent):
        return None, None

    requested_units = resolve_units(command, site, aliases)
    requested_keys = {unit.key.casefold() for unit in requested_units}
    candidates = [
        widget for widget in widgets
        if str(widget.get("type", "")).casefold() == "trend"
        and (not requested_keys or str(widget.get("unit_key", "")).casefold() in requested_keys)
    ]
    if not candidates:
        scope = f" στη μονάδα {requested_units[0].name}" if len(requested_units) == 1 else ""
        return {"action": "answer", "read_only": True, "requires_confirmation": False}, f"Δεν υπάρχουν γραφήματα για αφαίρεση{scope}."

    target_ids = [str(widget.get("id", "")) for widget in candidates if widget.get("id")]
    if len(requested_units) == 1:
        message = f"Αφαίρεσα και τα {len(target_ids)} γραφήματα από τη μονάδα {requested_units[0].name}."
    else:
        message = f"Αφαίρεσα και τα {len(target_ids)} γραφήματα από το dashboard."
    return {
        "action": "remove_widgets",
        "target_ids": target_ids,
        "read_only": True,
        "requires_confirmation": False,
    }, message


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


@router.post("/command")
def dashboard_command(request: DashboardCommandRequest) -> dict[str, object]:
    store = DashboardStore()
    dialogue = DashboardDialogueStore()
    current = store.get(request.workspace)
    current_widgets = current.get("widgets")
    if not isinstance(current_widgets, list):
        current_widgets = []

    try:
        site = load_site_model()
        aliases = dialogue.aliases()

        # Preserve what the user explicitly asked for before any planner runs.
        # This is intentionally separate from the unit that the generated widget
        # ultimately receives, so a later correction can repair a wrong action.
        explicit_units = resolve_units(request.command, site, aliases)
        if len(explicit_units) == 1:
            dialogue.remember_requested_unit(request.workspace, explicit_units[0].key)

        state = dialogue.get_state(request.workspace)

        plan, message = _bulk_remove_plan(request.command, site, aliases, current_widgets)
        if plan is None:
            plan, message = contextual_plan(
                request.command,
                site,
                state,
                current_widgets,
                learned_aliases=aliases,
            )

        if plan is None:
            working_command = _canonicalize_unit_references(request.command, site, aliases)
            plan = plan_dashboard_command(working_command, site, current_widgets=current_widgets)
            message = None

            folded = request.command.casefold()
            if any(token in folded for token in ("όχι", "οχι", "εννοώ", "εννοω", "λάθος", "λαθος")):
                corrected_units = resolve_units(folded, site, aliases)
                if len(corrected_units) == 1:
                    corrected = corrected_units[0]
                    for token in (corrected.name, corrected.key, *getattr(corrected, "aliases", ())):
                        if token and token.casefold() in folded:
                            dialogue.learn_alias(token, corrected.key)

        _validate_unit_intent(request.command, site, aliases, plan)

    except DashboardCommandError as exc:
        message = str(exc)
        plan = {
            "action": "clarify",
            "read_only": True,
            "requires_confirmation": False,
            "needs_clarification": True,
        }
        dialogue.remember(request.workspace, request.command, plan, current, message)
        return {"plan": plan, "workspace": current, "message": message, "needs_clarification": True}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if str(plan.get("action", "")) == "remove_widgets":
        workspace = _apply_bulk_remove(store, request.workspace, current, plan)
    else:
        workspace = store.apply_plan(request.workspace, plan)

    dialogue.remember(request.workspace, request.command, plan, workspace, message)
    return {
        "plan": plan,
        "workspace": workspace,
        "message": message,
        "needs_clarification": bool(plan.get("needs_clarification", False)),
    }
