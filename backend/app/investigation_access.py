"""Authorization helpers for durable investigation memory."""
from __future__ import annotations
from .agent_tools import ToolContext
from .investigation_store import Investigation

class InvestigationAccessError(PermissionError):
    pass

def authorize_investigation(item:Investigation,context:ToolContext)->None:
    # Do not reveal which check failed to callers.
    if item.user_id != context.actor_id:
        raise InvestigationAccessError("Investigation is not available in the active authorization context")
    unit=(item.unit_key or str(item.resume_context.get("unit_key") or "")).casefold()
    if unit and not context.access.permits_scope(context.refinery,scope_kind=context.scope_kind,scope_id=unit):
        raise InvestigationAccessError("Investigation is not available in the active authorization context")

def visible_investigations(items:list[Investigation],context:ToolContext)->list[Investigation]:
    visible=[]
    for item in items:
        try: authorize_investigation(item,context)
        except InvestigationAccessError: continue
        visible.append(item)
    return visible
