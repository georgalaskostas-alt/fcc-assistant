from __future__ import annotations

import json
from pathlib import Path


class DashboardStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "dashboards.json")

    def _load(self) -> dict[str, object]:
        if not self.path.exists(): return {"workspaces": {}}
        try: payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {"workspaces": {}}
        return payload if isinstance(payload, dict) and isinstance(payload.get("workspaces"), dict) else {"workspaces": {}}

    def _save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True); tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"); tmp.replace(self.path)

    def get(self, workspace: str) -> dict[str, object]:
        payload = self._load(); workspaces = payload["workspaces"]; assert isinstance(workspaces, dict); current = workspaces.get(workspace)
        return current if isinstance(current, dict) else {"workspace": workspace, "title": "Operations Overview", "widgets": []}

    def put(self, workspace: str, config: dict[str, object]) -> dict[str, object]:
        payload = self._load(); workspaces = payload["workspaces"]; assert isinstance(workspaces, dict)
        stored = {"workspace": workspace, **config}; workspaces[workspace] = stored; self._save(payload); return stored

    def _normalized_widgets(self, current: dict[str, object]) -> list[dict[str, object]]:
        raw = current.get("widgets"); widgets: list[dict[str, object]] = []
        if isinstance(raw, list):
            for index, item in enumerate(raw):
                if not isinstance(item, dict): continue
                w = dict(item); layout = w.get("layout")
                if not isinstance(layout, dict): layout = {"order": index, "width": 12 if w.get("type") == "trend" else 6 if w.get("type") == "summary" else 4, "height": "tall" if w.get("type") == "trend" else "normal" if w.get("type") == "summary" else "compact"}
                else: layout = {"order": int(layout.get("order", index)), "width": int(layout.get("width", 6)), "height": str(layout.get("height", "normal"))}
                w["layout"] = layout; widgets.append(w)
        widgets.sort(key=lambda w: int(w.get("layout", {}).get("order", 0)) if isinstance(w.get("layout"), dict) else 0)
        for i, w in enumerate(widgets): w["layout"]["order"] = i  # type: ignore[index]
        return widgets

    def _append_widget(self, widgets: list[dict[str, object]], widget: dict[str, object]) -> list[dict[str, object]]:
        updated = [w for w in widgets if w.get("id") != widget.get("id")]; candidate = dict(widget); layout = candidate.get("layout")
        if not isinstance(layout, dict): layout = {"order": len(updated), "width": 6, "height": "normal"}
        else: layout = {**layout, "order": len(updated)}
        candidate["layout"] = layout; updated.append(candidate); return updated

    def _apply_to_config(self, current: dict[str, object], plan: dict[str, object]) -> dict[str, object]:
        action = str(plan.get("action", "")); result = dict(current); widgets = self._normalized_widgets(result)
        if action in {"answer", "clarify"}: return result
        if action == "add_widget":
            w = plan.get("widget")
            if isinstance(w, dict): widgets = self._append_widget(widgets, w)
        elif action == "add_widgets":
            raw = plan.get("widgets")
            if isinstance(raw, list):
                for w in raw:
                    if isinstance(w, dict): widgets = self._append_widget(widgets, w)
        elif action in {"remove_widget", "remove_widgets"}:
            ids = {str(plan.get("target_id", ""))} if action == "remove_widget" else {str(v) for v in plan.get("target_ids", []) if isinstance(v, (str, int))}
            widgets = [w for w in widgets if str(w.get("id", "")) not in ids]
        elif action == "replace_widget":
            target_id = str(plan.get("target_id", "")); replacement = plan.get("widget")
            if isinstance(replacement, dict):
                found = False
                for i, old in enumerate(widgets):
                    if str(old.get("id", "")) == target_id:
                        candidate = dict(replacement); candidate["layout"] = dict(old.get("layout", {})); widgets[i] = candidate; found = True; break
                if not found: widgets = self._append_widget(widgets, replacement)
        elif action == "update_widgets":
            ids = {str(v) for v in plan.get("target_ids", []) if isinstance(v, (str, int))}
            period = str(plan.get("period", "")).strip()
            if ids and period:
                for w in widgets:
                    if str(w.get("id", "")) in ids:
                        w["period"] = period
        elif action == "resize_widget":
            target_id = str(plan.get("target_id", ""))
            for w in widgets:
                if str(w.get("id", "")) == target_id:
                    layout = w.get("layout"); layout = dict(layout) if isinstance(layout, dict) else {}
                    layout["width"] = min(12, max(3, int(plan.get("width", layout.get("width", 6))))); layout["height"] = str(plan.get("height", layout.get("height", "normal"))); w["layout"] = layout; break
        elif action == "move_between":
            target_id = str(plan.get("target_id", "")); target = next((w for w in widgets if str(w.get("id", "")) == target_id), None)
            if target:
                without = [w for w in widgets if str(w.get("id", "")) != target_id]; pos = {str(w.get("id")): i for i, w in enumerate(without)}; a, b = str(plan.get("first_id", "")), str(plan.get("second_id", ""))
                if a in pos and b in pos: without.insert(min(pos[a], pos[b]) + 1, target); widgets = without
        for i, w in enumerate(widgets):
            layout = w.get("layout"); layout = dict(layout) if isinstance(layout, dict) else {}; layout["order"] = i; w["layout"] = layout
        result["widgets"] = widgets; return result

    def apply_plan(self, workspace: str, plan: dict[str, object]) -> dict[str, object]:
        return self.put(workspace, self._apply_to_config(self.get(workspace), plan))

    def apply_transaction(self, workspace: str, plans: list[dict[str, object]]) -> dict[str, object]:
        """Apply an already validated plan list atomically: one final disk write."""
        current = self.get(workspace)
        for plan in plans: current = self._apply_to_config(current, plan)
        return self.put(workspace, current)
