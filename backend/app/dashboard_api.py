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


def _canonicalize_learned_aliases(command: str, aliases: dict[str, str]) -> str:
    """Keep the user's natural phrase but append canonical unit keys for learned aliases.

    The deterministic planner can then resolve the unit without requiring the
    engineer to repeat exact internal keys such as `hcu`.
    """
    folded = command.casefold()
    canonical_keys = [unit_key for alias, unit_key in aliases.items() if alias in folded]
    if not canonical_keys:
        return command
    return f"{command} {' '.join(dict.fromkeys(canonical_keys))}"


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
        state = dialogue.get_state(request.workspace)

        # First resolve conversational references and compound follow-ups such as
        # “πού έβαλες το τελευταίο γράφημα;” or “βγάλ' το από το FCC και βάλ' το
        # στο Hydrocracker”. These require dialogue state, not regex-only parsing.
        plan, message = contextual_plan(
            request.command,
            site,
            state,
            current_widgets,
            learned_aliases=aliases,
        )

        if plan is None:
            working_command = _canonicalize_learned_aliases(request.command, aliases)
            plan = plan_dashboard_command(working_command, site, current_widgets=current_widgets)
            message = None

            # When a user explicitly corrects a unit, persist the natural unit
            # name/key as a local alias. This is lightweight local learning, not
            # remote model training and no refinery data leaves the machine.
            folded = request.command.casefold()
            if any(token in folded for token in ("όχι", "οχι", "εννοώ", "εννοω", "λάθος", "λαθος")):
                corrected_units = resolve_units(folded, site, aliases)
                if len(corrected_units) == 1:
                    corrected = corrected_units[0]
                    for token in (corrected.name, corrected.key, *getattr(corrected, "aliases", ())):
                        if token and token.casefold() in folded:
                            dialogue.learn_alias(token, corrected.key)

    except (DashboardCommandError, ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workspace = store.apply_plan(request.workspace, plan)
    dialogue.remember(request.workspace, request.command, plan, workspace, message)
    return {"plan": plan, "workspace": workspace, "message": message}
