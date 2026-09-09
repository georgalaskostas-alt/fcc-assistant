from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()
_PATH = Path.home() / ".fcc-assistant" / "diagnostic-trace.json"
_MAX_EVENTS = 80


def append_trace(stage: str, payload: dict[str, Any]) -> None:
    event = {"ts": datetime.now(timezone.utc).isoformat(), "stage": stage, "payload": payload}
    with _LOCK:
        events: list[dict[str, Any]] = []
        if _PATH.exists():
            try:
                raw = json.loads(_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    events = [x for x in raw if isinstance(x, dict)]
            except (OSError, json.JSONDecodeError):
                events = []
        events.append(event)
        events = events[-_MAX_EVENTS:]
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_PATH)


def recent_trace(limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(limit, _MAX_EVENTS))
    with _LOCK:
        if not _PATH.exists():
            return []
        try:
            raw = json.loads(_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    return [x for x in raw if isinstance(x, dict)][-limit:] if isinstance(raw, list) else []


def clear_trace() -> None:
    with _LOCK:
        try:
            _PATH.unlink(missing_ok=True)
        except OSError:
            pass
