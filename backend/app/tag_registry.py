from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TagDefinition:
    key: str
    name: str
    group: str
    pi_tag: str
    web_id: str | None = None
    unit: str | None = None
    description: str | None = None


class TagRegistryError(RuntimeError):
    pass


class TagRegistry:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._tags = self._load_tags()

    def _load_tags(self) -> list[TagDefinition]:
        if not self.config_path.exists():
            raise TagRegistryError(f"Tag configuration not found: {self.config_path}")

        try:
            payload: dict[str, Any] = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TagRegistryError(f"Could not load tag configuration: {exc}") from exc

        tags: list[TagDefinition] = []
        for raw in payload.get("tags", []):
            try:
                tags.append(
                    TagDefinition(
                        key=str(raw["key"]).strip(),
                        name=str(raw["name"]).strip(),
                        group=str(raw["group"]).strip(),
                        pi_tag=str(raw["pi_tag"]).strip(),
                        web_id=(str(raw["web_id"]).strip() if raw.get("web_id") else None),
                        unit=(str(raw["unit"]).strip() if raw.get("unit") else None),
                        description=(
                            str(raw["description"]).strip() if raw.get("description") else None
                        ),
                    )
                )
            except KeyError as exc:
                raise TagRegistryError(f"Missing required tag field: {exc.args[0]}") from exc

        return tags

    def list(self) -> list[TagDefinition]:
        return list(self._tags)

    def find(self, query: str) -> list[TagDefinition]:
        needle = query.strip().casefold()
        if not needle:
            return self.list()

        ranked: list[tuple[int, TagDefinition]] = []
        for tag in self._tags:
            searchable = {
                tag.key.casefold(),
                tag.name.casefold(),
                tag.group.casefold(),
                tag.pi_tag.casefold(),
                (tag.description or "").casefold(),
            }

            if needle in {tag.key.casefold(), tag.name.casefold(), tag.pi_tag.casefold()}:
                score = 0
            elif any(value.startswith(needle) for value in searchable):
                score = 1
            elif any(needle in value for value in searchable):
                score = 2
            else:
                continue

            ranked.append((score, tag))

        ranked.sort(key=lambda item: (item[0], item[1].group, item[1].name))
        return [tag for _, tag in ranked]

    def get(self, key: str) -> TagDefinition | None:
        lookup = key.strip().casefold()
        for tag in self._tags:
            if tag.key.casefold() == lookup:
                return tag
        return None
