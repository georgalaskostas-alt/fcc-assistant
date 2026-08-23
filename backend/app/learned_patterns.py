from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

PatternStatus = Literal["candidate", "approved", "rejected"]
PatternEvidence = Literal["repeated_association", "engineering_hypothesis", "approved_unit_knowledge"]


@dataclass(frozen=True)
class LearnedPattern:
    id: str
    unit_key: str
    statement: str
    context: dict[str, float | str]
    outcome: dict[str, float | str]
    comparable_episodes: int
    confidence: float
    evidence_level: PatternEvidence = "repeated_association"
    status: PatternStatus = "candidate"
    engineer_note: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    created_at: str = ""


class LearnedPatternStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "learned-patterns.json")

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def add_candidate(
        self,
        *,
        unit_key: str,
        statement: str,
        context: dict[str, float | str],
        outcome: dict[str, float | str],
        comparable_episodes: int,
        confidence: float,
    ) -> LearnedPattern:
        if comparable_episodes < 2:
            raise ValueError("A repeated pattern requires at least two comparable episodes")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        pattern = LearnedPattern(
            id=str(uuid4()),
            unit_key=unit_key.strip().casefold(),
            statement=statement.strip(),
            context=dict(context),
            outcome=dict(outcome),
            comparable_episodes=int(comparable_episodes),
            confidence=float(confidence),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        rows = self._load()
        rows.append(asdict(pattern))
        self._save(rows)
        return pattern

    def list(self, *, unit_key: str | None = None, status: PatternStatus | None = None) -> list[LearnedPattern]:
        result: list[LearnedPattern] = []
        for row in self._load():
            try:
                pattern = LearnedPattern(**row)
            except TypeError:
                continue
            if unit_key and pattern.unit_key != unit_key.casefold():
                continue
            if status and pattern.status != status:
                continue
            result.append(pattern)
        return result

    def review(
        self,
        pattern_id: str,
        *,
        status: Literal["approved", "rejected"],
        reviewed_by: str,
        engineer_note: str = "",
    ) -> LearnedPattern:
        rows = self._load()
        now = datetime.now(timezone.utc).isoformat()
        updated: LearnedPattern | None = None
        for index, row in enumerate(rows):
            if str(row.get("id")) != pattern_id:
                continue
            payload = dict(row)
            payload["status"] = status
            payload["reviewed_by"] = reviewed_by.strip()
            payload["engineer_note"] = engineer_note.strip()
            payload["reviewed_at"] = now
            payload["evidence_level"] = "approved_unit_knowledge" if status == "approved" else "repeated_association"
            updated = LearnedPattern(**payload)
            rows[index] = asdict(updated)
            break
        if updated is None:
            raise KeyError(pattern_id)
        self._save(rows)
        return updated
