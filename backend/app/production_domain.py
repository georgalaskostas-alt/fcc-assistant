from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ProductionRecord:
    id: str
    scope_kind: str
    scope_id: str
    period_start: str
    period_end: str
    metric: str
    actual: float
    plan: float
    unit: str
    source: str = "manual_or_connector"
    created_at: str = ""

    @property
    def variance(self) -> float:
        return self.actual - self.plan

    @property
    def attainment(self) -> float | None:
        if self.plan == 0:
            return None
        return self.actual / self.plan


class ProductionStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "production.json")

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

    def add(
        self,
        *,
        scope_kind: str,
        scope_id: str,
        period_start: str,
        period_end: str,
        metric: str,
        actual: float,
        plan: float,
        unit: str,
        source: str = "manual_or_connector",
    ) -> ProductionRecord:
        start = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(period_end.replace("Z", "+00:00"))
        if end <= start:
            raise ValueError("period_end must be after period_start")
        if scope_kind not in {"refinery", "complex", "unit"}:
            raise ValueError("scope_kind must be refinery, complex or unit")
        if not scope_id.strip() or not metric.strip():
            raise ValueError("scope_id and metric are required")

        record = ProductionRecord(
            id=str(uuid4()),
            scope_kind=scope_kind,
            scope_id=scope_id.strip().casefold(),
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            metric=metric.strip(),
            actual=float(actual),
            plan=float(plan),
            unit=unit.strip(),
            source=source.strip() or "manual_or_connector",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        rows = self._load()
        rows.append(asdict(record))
        self._save(rows)
        return record

    def list(self, *, scope_kind: str | None = None, scope_id: str | None = None) -> list[ProductionRecord]:
        result: list[ProductionRecord] = []
        for row in self._load():
            try:
                record = ProductionRecord(**row)
            except TypeError:
                continue
            if scope_kind and record.scope_kind != scope_kind:
                continue
            if scope_id and record.scope_id != scope_id.casefold():
                continue
            result.append(record)
        return result

    def summary(self, *, scope_kind: str, scope_id: str) -> dict[str, object]:
        records = self.list(scope_kind=scope_kind, scope_id=scope_id)
        rows: list[dict[str, object]] = []
        for record in records:
            rows.append(
                {
                    **asdict(record),
                    "variance": record.variance,
                    "attainment": record.attainment,
                }
            )
        losses = [row for row in rows if isinstance(row.get("variance"), (int, float)) and float(row["variance"]) < 0]
        losses.sort(key=lambda row: float(row["variance"]))
        return {
            "scope_kind": scope_kind,
            "scope_id": scope_id,
            "count": len(rows),
            "records": rows,
            "negative_variances": losses,
        }
