from __future__ import annotations

import json
from pathlib import Path


class DashboardStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "dashboards.json")

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"workspaces": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workspaces": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("workspaces"), dict):
            return {"workspaces": {}}
        return payload

    def _save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, workspace: str) -> dict[str, object]:
        payload = self._load()
        workspaces = payload["workspaces"]
        assert isinstance(workspaces, dict)
        current = workspaces.get(workspace)
        if isinstance(current, dict):
            return current
        return {"workspace": workspace, "title": "Operations Overview", "widgets": []}

    def put(self, workspace: str, config: dict[str, object]) -> dict[str, object]:
        payload = self._load()
        workspaces = payload["workspaces"]
        assert isinstance(workspaces, dict)
        stored = {"workspace": workspace, **config}
        workspaces[workspace] = stored
        self._save(payload)
        return stored

    def add_widget(self, workspace: str, widget: dict[str, object]) -> dict[str, object]:
        current = self.get(workspace)
        widgets = current.get("widgets")
        if not isinstance(widgets, list):
            widgets = []
        widget_id = widget.get("id")
        widgets = [item for item in widgets if not (isinstance(item, dict) and item.get("id") == widget_id)]
        widgets.append(widget)
        current["widgets"] = widgets
        return self.put(workspace, current)
