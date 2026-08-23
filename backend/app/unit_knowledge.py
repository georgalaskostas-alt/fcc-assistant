from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


APPROVAL_STATES = {"draft", "approved", "retired"}


class UnitKnowledgeError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_effective(item: dict[str, Any], at: datetime) -> bool:
    if str(item.get("status", "draft")) != "approved":
        return False
    start = _parse_time(str(item.get("effective_from") or ""))
    end = _parse_time(str(item.get("effective_to") or ""))
    if start and at < start:
        return False
    if end and at >= end:
        return False
    return True


class UnitKnowledgeStore:
    """Local versioned operational knowledge for refinery process units.

    The store contains engineering context only. It never writes to PI/DCS and
    never mutates the original manual files. Manual metadata, revamps and
    engineer-approved operational overrides are kept as separate auditable
    records so historical analysis can resolve the knowledge that was effective
    at a specific point in time.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "unit-knowledge.json")

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": 1, "units": {}}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("units"), dict):
            return self._empty()
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _unit(self, payload: dict[str, Any], unit_key: str) -> dict[str, Any]:
        key = unit_key.strip().casefold()
        if not key:
            raise UnitKnowledgeError("unit_key is required")
        units = payload["units"]
        unit = units.get(key)
        if not isinstance(unit, dict):
            unit = {
                "unit_key": key,
                "knowledge_status": "draft",
                "manuals": [],
                "revamps": [],
                "overrides": [],
                "notes": [],
                "updated_at": _utc_now(),
            }
            units[key] = unit
        return unit

    def get_unit(self, unit_key: str) -> dict[str, Any]:
        payload = self._load()
        unit = self._unit(payload, unit_key)
        return json.loads(json.dumps(unit))

    def set_knowledge_status(self, unit_key: str, status: str) -> dict[str, Any]:
        normalized = status.strip().casefold()
        if normalized not in APPROVAL_STATES:
            raise UnitKnowledgeError(f"Invalid knowledge status: {status}")
        payload = self._load()
        unit = self._unit(payload, unit_key)
        unit["knowledge_status"] = normalized
        unit["updated_at"] = _utc_now()
        self._save(payload)
        return unit

    def add_manual(
        self,
        unit_key: str,
        *,
        title: str,
        revision: str = "",
        source_path: str = "",
        summary: str = "",
        document_date: str | None = None,
        status: str = "draft",
    ) -> dict[str, Any]:
        if not title.strip():
            raise UnitKnowledgeError("Manual title is required")
        normalized_status = status.strip().casefold()
        if normalized_status not in APPROVAL_STATES:
            raise UnitKnowledgeError(f"Invalid manual status: {status}")
        payload = self._load()
        unit = self._unit(payload, unit_key)
        record = {
            "id": f"manual-{uuid4().hex}",
            "title": title.strip(),
            "revision": revision.strip(),
            "source_path": source_path.strip(),
            "summary": summary.strip(),
            "document_date": document_date,
            "status": normalized_status,
            "created_at": _utc_now(),
        }
        unit["manuals"].append(record)
        unit["updated_at"] = _utc_now()
        self._save(payload)
        return record

    def add_revamp(
        self,
        unit_key: str,
        *,
        title: str,
        description: str,
        effective_from: str,
        effective_to: str | None = None,
        approved_by: str = "",
        status: str = "draft",
    ) -> dict[str, Any]:
        if not title.strip() or not description.strip():
            raise UnitKnowledgeError("Revamp title and description are required")
        _parse_time(effective_from)
        _parse_time(effective_to)
        normalized_status = status.strip().casefold()
        if normalized_status not in APPROVAL_STATES:
            raise UnitKnowledgeError(f"Invalid revamp status: {status}")
        payload = self._load()
        unit = self._unit(payload, unit_key)
        record = {
            "id": f"revamp-{uuid4().hex}",
            "title": title.strip(),
            "description": description.strip(),
            "effective_from": effective_from,
            "effective_to": effective_to,
            "approved_by": approved_by.strip(),
            "status": normalized_status,
            "created_at": _utc_now(),
        }
        unit["revamps"].append(record)
        unit["updated_at"] = _utc_now()
        self._save(payload)
        return record

    def add_override(
        self,
        unit_key: str,
        *,
        subject: str,
        manual_value: str,
        current_value: str,
        reason: str,
        effective_from: str,
        effective_to: str | None = None,
        manual_reference: str = "",
        approved_by: str = "",
        status: str = "draft",
    ) -> dict[str, Any]:
        if not subject.strip() or not current_value.strip() or not reason.strip():
            raise UnitKnowledgeError("Override subject, current_value and reason are required")
        _parse_time(effective_from)
        _parse_time(effective_to)
        normalized_status = status.strip().casefold()
        if normalized_status not in APPROVAL_STATES:
            raise UnitKnowledgeError(f"Invalid override status: {status}")
        payload = self._load()
        unit = self._unit(payload, unit_key)
        record = {
            "id": f"override-{uuid4().hex}",
            "subject": subject.strip(),
            "manual_value": manual_value.strip(),
            "current_value": current_value.strip(),
            "reason": reason.strip(),
            "manual_reference": manual_reference.strip(),
            "effective_from": effective_from,
            "effective_to": effective_to,
            "approved_by": approved_by.strip(),
            "status": normalized_status,
            "created_at": _utc_now(),
        }
        unit["overrides"].append(record)
        unit["updated_at"] = _utc_now()
        self._save(payload)
        return record

    def effective_context(self, unit_key: str, at_time: str | None = None) -> dict[str, Any]:
        unit = self.get_unit(unit_key)
        at = _parse_time(at_time) if at_time else datetime.now(timezone.utc)
        assert at is not None
        approved_manuals = [item for item in unit.get("manuals", []) if item.get("status") == "approved"]
        effective_revamps = [item for item in unit.get("revamps", []) if _is_effective(item, at)]
        effective_overrides = [item for item in unit.get("overrides", []) if _is_effective(item, at)]
        return {
            "unit_key": unit["unit_key"],
            "knowledge_status": unit.get("knowledge_status", "draft"),
            "at_time": at.isoformat().replace("+00:00", "Z"),
            "manuals": approved_manuals,
            "revamps": effective_revamps,
            "overrides": effective_overrides,
            "read_only_process_access": True,
        }
