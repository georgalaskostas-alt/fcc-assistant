from __future__ import annotations

from fastapi import APIRouter

from .dashboard_dialogue import DashboardDialogueStore
from .diagnostic_trace import recent_trace

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


@router.get("/dashboard")
def dashboard_debug(workspace: str = "default", limit: int = 80) -> dict[str, object]:
    """Local-only development inspector for conversation and execution trace."""
    state = DashboardDialogueStore().get_state(workspace)
    turns = state.get("recent_turns")
    return {
        "local_only": True,
        "workspace": workspace,
        "conversation": list(turns) if isinstance(turns, list) else [],
        "state": state,
        "events": recent_trace(max(1, min(limit, 200))),
    }
