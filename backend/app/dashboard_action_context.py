from __future__ import annotations

import json
from pathlib import Path


class DashboardActionContextStore:
    """Small persistent context containing only verified workspace mutations."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "dashboard-action-context.json")

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"workspaces": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workspaces": {}}
        return payload if isinstance(payload, dict) else {"workspaces": {}}

    def _save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, workspace: str) -> dict[str, object]:
        payload = self._load()
        workspaces = payload.get("workspaces")
        value = workspaces.get(workspace) if isinstance(workspaces, dict) else None
        return dict(value) if isinstance(value, dict) else {}

    def remember(self, workspace: str, plan: dict[str, object], workspace_payload: dict[str, object]) -> None:
        touched: list[str] = []
        action = str(plan.get("action", ""))
        steps = plan.get("steps") if action == "transaction" else [plan]
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_action = str(step.get("action", ""))
                if step_action in {"add_widget", "replace_widget"}:
                    widget = step.get("widget")
                    if isinstance(widget, dict) and widget.get("id"):
                        touched.append(str(widget["id"]))
                elif step_action == "add_widgets":
                    widgets = step.get("widgets")
                    if isinstance(widgets, list):
                        touched.extend(str(widget["id"]) for widget in widgets if isinstance(widget, dict) and widget.get("id"))
                elif step_action == "update_widgets":
                    ids = step.get("target_ids")
                    if isinstance(ids, list):
                        touched.extend(str(value) for value in ids)
                elif step_action == "remove_widget" and step.get("target_id"):
                    touched.append(str(step["target_id"]))
                elif step_action == "remove_widgets":
                    ids = step.get("target_ids")
                    if isinstance(ids, list):
                        touched.extend(str(value) for value in ids)

        if not touched or action in {"answer", "clarify"}:
            return

        current = workspace_payload.get("widgets")
        current_ids = {str(widget.get("id")) for widget in current if isinstance(widget, dict) and widget.get("id")} if isinstance(current, list) else set()
        existing_touched = [value for value in touched if value in current_ids]

        payload = self._load()
        workspaces = payload.setdefault("workspaces", {})
        if not isinstance(workspaces, dict):
            workspaces = {}
            payload["workspaces"] = workspaces
        workspaces[workspace] = {
            "last_action": action,
            "last_touched_widget_ids": existing_touched,
        }
        self._save(payload)
