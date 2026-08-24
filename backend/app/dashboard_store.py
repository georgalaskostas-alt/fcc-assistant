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

    def _normalized_widgets(self, current: dict[str, object]) -> list[dict[str, object]]:
        widgets = current.get("widgets")
        if not isinstance(widgets, list):
            return []
        normalized: list[dict[str, object]] = []
        for index, item in enumerate(widgets):
            if not isinstance(item, dict):
                continue
            widget = dict(item)
            layout = widget.get("layout")
            if not isinstance(layout, dict):
                width = 12 if widget.get("type") == "trend" else 6 if widget.get("type") == "summary" else 4
                height = "tall" if widget.get("type") == "trend" else "normal" if widget.get("type") == "summary" else "compact"
                layout = {"order": index, "width": width, "height": height}
            else:
                layout = {"order": int(layout.get("order", index)), "width": int(layout.get("width", 6)), "height": str(layout.get("height", "normal"))}
            widget["layout"] = layout
            normalized.append(widget)
        normalized.sort(key=lambda item: int(item.get("layout", {}).get("order", 0)) if isinstance(item.get("layout"), dict) else 0)
        for index, widget in enumerate(normalized):
            layout = widget["layout"]
            assert isinstance(layout, dict)
            layout["order"] = index
        return normalized

    def _append_widget(self, widgets: list[dict[str, object]], widget: dict[str, object]) -> list[dict[str, object]]:
        widget_id = widget.get("id")
        updated = [item for item in widgets if item.get("id") != widget_id]
        candidate = dict(widget)
        layout = candidate.get("layout")
        if not isinstance(layout, dict):
            layout = {"order": len(updated), "width": 6, "height": "normal"}
        else:
            layout = dict(layout)
            layout["order"] = len(updated)
        candidate["layout"] = layout
        updated.append(candidate)
        return updated

    def add_widget(self, workspace: str, widget: dict[str, object]) -> dict[str, object]:
        current = self.get(workspace)
        widgets = self._append_widget(self._normalized_widgets(current), widget)
        current["widgets"] = widgets
        return self.put(workspace, current)

    def add_widgets(self, workspace: str, new_widgets: list[dict[str, object]]) -> dict[str, object]:
        current = self.get(workspace)
        widgets = self._normalized_widgets(current)
        for widget in new_widgets:
            widgets = self._append_widget(widgets, widget)
        for index, widget in enumerate(widgets):
            layout = widget.get("layout")
            if not isinstance(layout, dict):
                layout = {}
                widget["layout"] = layout
            layout["order"] = index
        current["widgets"] = widgets
        return self.put(workspace, current)

    def apply_plan(self, workspace: str, plan: dict[str, object]) -> dict[str, object]:
        action = plan.get("action")
        if action == "answer":
            return self.get(workspace)

        if action == "add_widget":
            widget = plan.get("widget")
            if isinstance(widget, dict):
                return self.add_widget(workspace, widget)
            return self.get(workspace)

        if action == "add_widgets":
            raw_widgets = plan.get("widgets")
            if isinstance(raw_widgets, list):
                valid = [widget for widget in raw_widgets if isinstance(widget, dict)]
                if valid:
                    return self.add_widgets(workspace, valid)
            return self.get(workspace)

        current = self.get(workspace)
        widgets = self._normalized_widgets(current)
        target_id = str(plan.get("target_id", ""))

        if action == "replace_widget":
            replacement = plan.get("widget")
            if not isinstance(replacement, dict):
                return current
            replaced = False
            for index, existing in enumerate(widgets):
                if str(existing.get("id")) != target_id:
                    continue
                candidate = dict(replacement)
                old_layout = existing.get("layout")
                candidate["layout"] = dict(old_layout) if isinstance(old_layout, dict) else {"order": index, "width": 6, "height": "normal"}
                widgets[index] = candidate
                replaced = True
                break
            if not replaced:
                widgets = self._append_widget(widgets, replacement)
            for index, widget in enumerate(widgets):
                layout = widget.get("layout")
                if not isinstance(layout, dict):
                    layout = {}
                    widget["layout"] = layout
                layout["order"] = index
            current["widgets"] = widgets
            return self.put(workspace, current)

        if action == "remove_widget":
            widgets = [widget for widget in widgets if str(widget.get("id")) != target_id]
            for index, widget in enumerate(widgets):
                layout = widget.get("layout")
                if not isinstance(layout, dict):
                    layout = {}
                    widget["layout"] = layout
                layout["order"] = index
            current["widgets"] = widgets
            return self.put(workspace, current)

        by_id = {str(widget.get("id")): widget for widget in widgets}
        target = by_id.get(target_id)
        if target is None:
            return current

        if action == "resize_widget":
            layout = target.get("layout")
            if not isinstance(layout, dict):
                layout = {}
                target["layout"] = layout
            width = int(plan.get("width", layout.get("width", 6)))
            layout["width"] = min(12, max(3, width))
            layout["height"] = str(plan.get("height", layout.get("height", "normal")))

        elif action == "move_between":
            first_id = str(plan.get("first_id", ""))
            second_id = str(plan.get("second_id", ""))
            without_target = [widget for widget in widgets if str(widget.get("id")) != target_id]
            positions = {str(widget.get("id")): index for index, widget in enumerate(without_target)}
            if first_id in positions and second_id in positions:
                insert_at = min(positions[first_id], positions[second_id]) + 1
                without_target.insert(insert_at, target)
                widgets = without_target

        for index, widget in enumerate(widgets):
            layout = widget.get("layout")
            if not isinstance(layout, dict):
                layout = {}
                widget["layout"] = layout
            layout["order"] = index

        current["widgets"] = widgets
        return self.put(workspace, current)
