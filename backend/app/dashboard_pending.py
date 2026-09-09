from __future__ import annotations

import json
from pathlib import Path


class DashboardPendingStore:
    """Small local-only store for incomplete conversational action frames."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "dashboard-pending.json")

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, workspace: str) -> dict[str, object] | None:
        value = self._load().get(workspace)
        return dict(value) if isinstance(value, dict) else None

    def set(self, workspace: str, frame: dict[str, object]) -> None:
        payload = self._load()
        payload[workspace] = dict(frame)
        self._save(payload)

    def clear(self, workspace: str) -> None:
        payload = self._load()
        if workspace in payload:
            payload.pop(workspace, None)
            self._save(payload)
