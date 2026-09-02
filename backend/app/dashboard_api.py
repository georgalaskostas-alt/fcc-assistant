from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .dashboard_action_context import DashboardActionContextStore
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
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


def _planned_unit_keys(plan: dict[str, object]) -> set[str]:
    keys: set[str] = set()
    for step in _steps(plan):
        if str(step.get("action", "")) in {"answer", "clarify", "remove_widget", "remove_widgets", "update_widgets", "resize_widget", "move_between"}:
            continue
        candidates: list[dict[str, object]] = []
        if isinstance(step.get("widget"), dict):
            candidates.append(step["widget"])  # type: ignore[arg-type]
        if isinstance(step.get("widgets"), list):
            candidates.extend(item for item in step["widgets"] if isinstance(item, dict))  # type: ignore[index]
        keys.update(str(item.get("unit_key", "")).casefold() for item in candidates if item.get("unit_key"))
    return keys


def _validate_unit_intent(command, site, aliases, plan) -> None:
    requested = {unit.key.casefold() for unit in resolve_units(command, site, aliases)}
    planned = _planned_unit_keys(plan)
    if requested and planned and not planned.issubset(requested):
        raise DashboardCommandError("Κατάλαβα διαφορετική μονάδα από αυτή που ζήτησες. Δεν άλλαξα τίποτα.")


def _validate_transaction(plan: dict[str, object]) -> list[dict[str, object]]:
    steps = _steps(plan)
    allowed = {"add_widget", "add_widgets", "remove_widget", "remove_widgets", "replace_widget", "update_widgets", "resize_widget", "move_between", "answer"}
    if not steps or any(str(step.get("action", "")) not in allowed for step in steps):
        raise DashboardCommandError("Δεν μπόρεσα να επαληθεύσω με ασφάλεια όλη τη σύνθετη εντολή. Δεν άλλαξα τίποτα.")
    return steps


def _metric_filter(text: str) -> str | None:
    compact = re.sub(r"[^a-z0-9α-ωάέήίόύώ]+", "", text.casefold())
    if any(token in compact for token in ("feedflow", "παροχηfeed", "τροφοδοσια")) or "feed" in text.casefold():
        return "feed"
    if any(token in compact for token in ("reactortemp", "reactortemperature", "θερμοκρασιαreactor", "θερμοκρασιααντιδραστηρα")):
        return "reactor"
    if "regenerator" in text.casefold() or "αναγεννη" in text.casefold():
        return "regenerator"
    return None


def _widget_matches_metric(widget: dict[str, object], metric_filter: str) -> bool:
    hay = " ".join([
        str(widget.get("id", "")),
        str(widget.get("title", "")),
        *(str(value) for value in (widget.get("tag_keys") or [])),
    ]).casefold()
    if metric_filter == "feed":
        return "feed" in hay
    if metric_filter == "reactor":
        return "reactor" in hay and "temp" in hay
    if metric_filter == "regenerator":
        return "regenerator" in hay
    return True


def _period_followup_plan(command, state, action_context, widgets, explicit_units):
    """Resolve period changes before the LLM when the target is verifiable.

    The resolver prefers the last *successfully mutated* widget batch for elliptical
    follow-ups ("κάν' τα 8 ώρες"), and uses explicit metric/unit wording when present.
    It never touches KPI/LIVE cards.
    """
    text = command.casefold().strip()
    match = re.search(r"(?<!\d)(\d{1,3})\s*(?:h|hr|hrs|hour|hours|ωρ(?:α|ες|ών)?|ωρες|ώρα|ώρες)(?!\w)", text, re.I)
    if not match:
        return None
    period = f"{int(match.group(1))}h"

    trends = [widget for widget in widgets if str(widget.get("type", "")).casefold() == "trend" and widget.get("id")]
    if not trends:
        return None

    unit_keys = {unit.key.casefold() for unit in explicit_units}
    if unit_keys:
        trends = [widget for widget in trends if str(widget.get("unit_key", "")).casefold() in unit_keys]

    graph_words = any(token in text for token in ("διάγραμ", "διαγραμ", "γράφημ", "γραφημ", "trend", "chart"))
    plural_followup = any(token in text for token in (
        "τελικά τα", "τελικα τα", "τα θέλω", "τα θελω", "κάν' τα", "καν' τα", "κάντα", "καντα",
        "και τα δύο", "και τα δυο", "και στις δύο", "και στις δυο", "στις δύο", "στις δυο", "both",
    ))

    metric = _metric_filter(text)
    if metric:
        trends = [widget for widget in trends if _widget_matches_metric(widget, metric)]

    touched_raw = action_context.get("last_touched_widget_ids") if isinstance(action_context, dict) else None
    touched = {str(value) for value in touched_raw} if isinstance(touched_raw, list) else set()
    if not metric and not unit_keys and plural_followup and touched:
        touched_trends = [widget for widget in trends if str(widget.get("id")) in touched]
        if touched_trends:
            trends = touched_trends

    prior_mutation = str(action_context.get("last_action", "")).casefold() in {"transaction", "add_widget", "add_widgets", "update_widgets", "replace_widget"}
    prior_dialogue_mutation = str(state.get("last_action", "")).casefold() in {"transaction", "add_widget", "add_widgets", "update_widgets", "replace_widget"}

    if not unit_keys and not metric and not graph_words and not (plural_followup and (prior_mutation or prior_dialogue_mutation or bool(touched))):
        return None
    if not trends:
        return None

    ids = [str(widget["id"]) for widget in trends]
    return {
        "action": "update_widgets",
        "target_ids": ids,
        "period": period,
        "read_only": True,
        "requires_confirmation": False,
    }, f"Έγινε. Άλλαξα {len(ids)} γραφήματα σε {period}."


def _legacy_plan(command, site, state, widgets, aliases):
    plan, message = contextual_plan(command, site, state, widgets, learned_aliases=aliases)
    if plan is not None:
        return plan, message
    resolved = resolve_units(command, site, aliases)
    working = f"{command} {' '.join(unit.key for unit in resolved)}" if resolved else command
    return plan_dashboard_command(working, site, current_widgets=widgets), None


def _safe_failure(request, current, widgets, dialogue, pending_store, route, exc):
    append_trace("command.error", {"command": request.command, "route": route, "error_type": type(exc).__name__, "error": str(exc)})
    message = "Δεν ολοκληρώθηκε η ενέργεια λόγω τοπικού σφάλματος. Δεν άλλαξα τίποτα."
    plan = {"action": "clarify", "read_only": True, "requires_confirmation": False, "needs_clarification": True}
    dialogue.remember(request.workspace, request.command, plan, current, message, previous_widgets=widgets)
    return {
        "plan": plan,
        "workspace": current,
        "message": message,
        "needs_clarification": True,
        "agent": route,
        "pending_intent": pending_store.get(request.workspace),
        "site": site_runtime_status(),
    }


@router.post("/command")
async def dashboard_command(request: DashboardCommandRequest) -> dict[str, object]:
    store = DashboardStore()
    dialogue = DashboardDialogueStore()
    pending_store = DashboardPendingStore()
    action_store = DashboardActionContextStore()
    current = store.get(request.workspace)
    raw = current.get("widgets")
    widgets = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    route = "unknown"

    try:
        site = load_site_model()
        aliases = dialogue.aliases()
        explicit = resolve_units(request.command, site, aliases)
        pending = pending_store.get(request.workspace)
        append_trace("command.received", {
            "command": request.command,
            "workspace": request.workspace,
            "explicit_units": [unit.key for unit in explicit],
            "pending_intent": pending,
            "widgets_before": [
                {"id": widget.get("id"), "unit_key": widget.get("unit_key"), "tag_keys": widget.get("tag_keys"), "type": widget.get("type"), "period": widget.get("period")}
                for widget in widgets
            ],
        })
        if len(explicit) == 1:
            dialogue.remember_requested_unit(request.workspace, explicit[0].key)
        state = dialogue.get_state(request.workspace)
        if pending is not None:
            state["pending_intent"] = pending

        deterministic_update = _period_followup_plan(request.command, state, action_store.get(request.workspace), widgets, explicit)
        if deterministic_update is not None:
            plan, message = deterministic_update
            route = "verified-context-update"
            append_trace("command.context_resolved", {"command": request.command, "plan": plan, "reason": "verified-period-followup"})
        else:
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
    except (ValueError, OSError, RuntimeError) as exc:
        return _safe_failure(request, current, widgets, dialogue, pending_store, route, exc)

    action = str(plan.get("action", ""))
    try:
        if action == "clarify":
            frame = plan.get("pending_intent")
            if isinstance(frame, dict):
                pending_store.set(request.workspace, frame)
                append_trace("command.pending", {"workspace": request.workspace, "pending_intent": frame})
            workspace = current
        else:
            workspace = store.apply_transaction(request.workspace, steps) if action == "transaction" else store.apply_plan(request.workspace, plan)
            if action != "answer":
                pending_store.clear(request.workspace)
    except OSError as exc:
        return _safe_failure(request, current, widgets, dialogue, pending_store, route, exc)

    append_trace("command.executed", {
        "command": request.command,
        "route": route,
        "plan": plan,
        "message": message,
        "pending_after": pending_store.get(request.workspace),
        "widgets_after": [
            {"id": widget.get("id"), "unit_key": widget.get("unit_key"), "tag_keys": widget.get("tag_keys"), "type": widget.get("type"), "period": widget.get("period")}
            for widget in (workspace.get("widgets") or []) if isinstance(widget, dict)
        ],
    })
    dialogue.remember(request.workspace, request.command, plan, workspace, message, previous_widgets=widgets)
    action_store.remember(request.workspace, plan, workspace)
    return {
        "plan": plan,
        "workspace": workspace,
        "message": message,
        "needs_clarification": bool(plan.get("needs_clarification", False)),
        "agent": route,
        "pending_intent": pending_store.get(request.workspace),
        "site": site_runtime_status(),
    }
