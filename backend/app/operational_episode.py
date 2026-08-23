from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

EpisodeKind = Literal[
    "stable",
    "feed_transition",
    "rate_change",
    "severity_change",
    "quality_correction",
    "constraint",
    "disturbance",
    "recovery",
    "startup",
    "shutdown",
    "other",
]

EvidenceLevel = Literal["observed", "repeated_association", "engineering_hypothesis", "approved_unit_knowledge"]


@dataclass(frozen=True)
class OperationalEpisode:
    id: str
    unit_key: str
    start_time: str
    end_time: str
    kind: EpisodeKind
    regime: str
    configuration_version: str = "current"
    inputs: dict[str, float | str] = field(default_factory=dict)
    operating_state: dict[str, float | str] = field(default_factory=dict)
    constraints: dict[str, float | str] = field(default_factory=dict)
    outputs: dict[str, float | str] = field(default_factory=dict)
    quality: dict[str, float | str] = field(default_factory=dict)
    outcomes: dict[str, float | str] = field(default_factory=dict)
    source: str = "process_history"
    created_at: str = ""


@dataclass(frozen=True)
class SimilarEpisode:
    episode: OperationalEpisode
    similarity: float
    matched_features: tuple[str, ...]


class OperationalEpisodeStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".fcc-assistant" / "operational-episodes.json")

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
        unit_key: str,
        start_time: str,
        end_time: str,
        kind: EpisodeKind,
        regime: str,
        configuration_version: str = "current",
        inputs: dict[str, float | str] | None = None,
        operating_state: dict[str, float | str] | None = None,
        constraints: dict[str, float | str] | None = None,
        outputs: dict[str, float | str] | None = None,
        quality: dict[str, float | str] | None = None,
        outcomes: dict[str, float | str] | None = None,
        source: str = "process_history",
    ) -> OperationalEpisode:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        if end <= start:
            raise ValueError("Episode end_time must be after start_time")
        if not unit_key.strip() or not regime.strip():
            raise ValueError("unit_key and regime are required")

        episode = OperationalEpisode(
            id=str(uuid4()),
            unit_key=unit_key.strip().casefold(),
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            kind=kind,
            regime=regime.strip(),
            configuration_version=configuration_version.strip() or "current",
            inputs=dict(inputs or {}),
            operating_state=dict(operating_state or {}),
            constraints=dict(constraints or {}),
            outputs=dict(outputs or {}),
            quality=dict(quality or {}),
            outcomes=dict(outcomes or {}),
            source=source.strip() or "process_history",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        rows = self._load()
        rows.append(asdict(episode))
        self._save(rows)
        return episode

    def list(self, unit_key: str | None = None, configuration_version: str | None = None) -> list[OperationalEpisode]:
        result: list[OperationalEpisode] = []
        for row in self._load():
            try:
                episode = OperationalEpisode(**row)
            except TypeError:
                continue
            if unit_key and episode.unit_key != unit_key.casefold():
                continue
            if configuration_version and episode.configuration_version != configuration_version:
                continue
            result.append(episode)
        return result

    @staticmethod
    def _flatten_context(episode: OperationalEpisode) -> dict[str, float | str]:
        result: dict[str, float | str] = {
            "regime": episode.regime,
            "kind": episode.kind,
            "configuration_version": episode.configuration_version,
        }
        for prefix, values in (
            ("input", episode.inputs),
            ("state", episode.operating_state),
            ("constraint", episode.constraints),
        ):
            for key, value in values.items():
                result[f"{prefix}.{key}"] = value
        return result

    @staticmethod
    def _feature_similarity(left: float | str, right: float | str) -> float:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            scale = max(abs(float(left)), abs(float(right)), 1.0)
            return max(0.0, 1.0 - abs(float(left) - float(right)) / scale)
        return 1.0 if str(left).casefold() == str(right).casefold() else 0.0

    def similar(
        self,
        *,
        unit_key: str,
        context: dict[str, float | str],
        configuration_version: str = "current",
        limit: int = 10,
    ) -> list[SimilarEpisode]:
        if not context:
            return []
        scored: list[SimilarEpisode] = []
        for episode in self.list(unit_key=unit_key, configuration_version=configuration_version):
            features = self._flatten_context(episode)
            common = sorted(set(context).intersection(features))
            if not common:
                continue
            values = [self._feature_similarity(context[key], features[key]) for key in common]
            scored.append(
                SimilarEpisode(
                    episode=episode,
                    similarity=round(sum(values) / len(values), 4),
                    matched_features=tuple(common),
                )
            )
        scored.sort(key=lambda item: item.similarity, reverse=True)
        return scored[: max(1, limit)]


def outcome_envelope(episodes: list[OperationalEpisode]) -> dict[str, dict[str, float]]:
    numeric: dict[str, list[float]] = {}
    for episode in episodes:
        for source in (episode.outputs, episode.quality, episode.outcomes):
            for key, value in source.items():
                if isinstance(value, (int, float)):
                    numeric.setdefault(key, []).append(float(value))
    envelope: dict[str, dict[str, float]] = {}
    for key, values in numeric.items():
        envelope[key] = {
            "count": float(len(values)),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
    return envelope
