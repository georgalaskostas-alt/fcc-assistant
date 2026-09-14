"""Durable refinery investigation/task memory for autonomous engineering work."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4


class InvestigationStatus(StrEnum):
    OPEN = "open"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class EvidenceRecord:
    source_type: str
    source_id: str
    summary: str
    provenance: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Investigation:
    id: str
    goal: str
    user_id: str
    unit_key: str | None = None
    status: InvestigationStatus = InvestigationStatus.OPEN
    created_at: str = ""
    updated_at: str = ""
    plan_id: str | None = None
    notes: list[str] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    conclusion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


class InvestigationStoreError(ValueError):
    pass


class InvestigationStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser() if path else Path.home() / ".fcc-assistant" / "investigations.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvestigationStoreError(f"Could not read investigations: {exc}") from exc
        if not isinstance(raw, dict):
            raise InvestigationStoreError("Investigation store root must be an object")
        return raw

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> Investigation:
        return Investigation(
            id=str(raw["id"]),
            goal=str(raw.get("goal") or ""),
            user_id=str(raw.get("user_id") or "unknown"),
            unit_key=raw.get("unit_key"),
            status=InvestigationStatus(str(raw.get("status") or InvestigationStatus.OPEN.value)),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
            plan_id=raw.get("plan_id"),
            notes=[str(item) for item in (raw.get("notes") or [])],
            evidence=[EvidenceRecord(**item) for item in (raw.get("evidence") or [])],
            artifacts=[dict(item) for item in (raw.get("artifacts") or []) if isinstance(item, dict)],
            conclusion=raw.get("conclusion"),
        )

    def create(self, *, goal: str, user_id: str, unit_key: str | None = None) -> Investigation:
        if not goal.strip():
            raise InvestigationStoreError("Investigation goal is required")
        now = self._now()
        item = Investigation(
            id=f"inv-{uuid4().hex}",
            goal=goal.strip(),
            user_id=user_id.strip() or "unknown",
            unit_key=unit_key.casefold() if unit_key else None,
            created_at=now,
            updated_at=now,
        )
        payload = self._load()
        payload[item.id] = item.to_dict()
        self._save(payload)
        return item

    def get(self, investigation_id: str) -> Investigation | None:
        raw = self._load().get(investigation_id)
        return self._from_dict(raw) if raw else None

    def list(self, *, user_id: str | None = None, status: InvestigationStatus | None = None) -> list[Investigation]:
        items = [self._from_dict(raw) for raw in self._load().values()]
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def update(self, investigation: Investigation) -> Investigation:
        investigation.updated_at = self._now()
        payload = self._load()
        payload[investigation.id] = investigation.to_dict()
        self._save(payload)
        return investigation

    def attach_plan(self, investigation_id: str, plan_id: str) -> Investigation:
        item = self._require(investigation_id)
        item.plan_id = plan_id
        item.status = InvestigationStatus.RUNNING
        return self.update(item)

    def add_evidence(self, investigation_id: str, evidence: EvidenceRecord) -> Investigation:
        item = self._require(investigation_id)
        item.evidence.append(evidence)
        return self.update(item)

    def add_artifact(self, investigation_id: str, artifact: dict[str, Any]) -> Investigation:
        item = self._require(investigation_id)
        item.artifacts.append(dict(artifact))
        return self.update(item)

    def complete(self, investigation_id: str, *, conclusion: str) -> Investigation:
        item = self._require(investigation_id)
        item.conclusion = conclusion.strip()
        item.status = InvestigationStatus.COMPLETED
        return self.update(item)

    def fail(self, investigation_id: str, *, note: str) -> Investigation:
        item = self._require(investigation_id)
        if note.strip():
            item.notes.append(note.strip())
        item.status = InvestigationStatus.FAILED
        return self.update(item)

    def _require(self, investigation_id: str) -> Investigation:
        item = self.get(investigation_id)
        if item is None:
            raise InvestigationStoreError(f"Unknown investigation: {investigation_id}")
        return item
