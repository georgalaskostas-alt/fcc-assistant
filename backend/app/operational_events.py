"""Read-only operational alarm/event contracts for autonomous investigations."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json
from typing import Any


@dataclass(frozen=True)
class OperationalEvent:
    id: str
    unit_key: str
    timestamp: str
    event_type: str
    source: str
    message: str
    severity: str = "info"
    tag_key: str | None = None
    equipment_key: str | None = None
    metadata: dict[str, Any] | None = None


class OperationalEventStore:
    """Local adapter now; replaceable by PI/AF/event-frame/alarm source later."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "operational-events.json")

    def _load(self) -> list[OperationalEvent]:
        if not self.path.exists(): return []
        try: rows = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return []
        result: list[OperationalEvent] = []
        for row in rows if isinstance(rows, list) else []:
            try: result.append(OperationalEvent(**row))
            except (TypeError, ValueError): continue
        return result

    def search(self, *, unit_key: str, start_time: str, end_time: str, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        terms = [term.casefold() for term in query.split() if term.strip()]
        hits: list[OperationalEvent] = []
        for event in self._load():
            if event.unit_key.casefold() != unit_key.casefold(): continue
            try: when = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            except ValueError: continue
            if not start <= when <= end: continue
            haystack = " ".join(filter(None, [event.event_type,event.source,event.message,event.severity,event.tag_key,event.equipment_key])).casefold()
            if terms and not any(term in haystack for term in terms): continue
            hits.append(event)
        hits.sort(key=lambda item: item.timestamp)
        return [asdict(item) for item in hits[:max(1, min(limit, 500))]]
