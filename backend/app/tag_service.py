from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .pi_client import PIWebAPIClient, PIWebAPIError
from .tag_registry import TagDefinition, TagRegistry, TagRegistryError
from .settings import get_settings


class TagServiceError(RuntimeError):
    pass


class TagService:
    def __init__(self) -> None:
        settings = get_settings()
        self.registry = TagRegistry(settings.tag_config_path)
        self.pi = PIWebAPIClient()

    def _require_tag(self, key: str) -> TagDefinition:
        tag = self.registry.get(key)
        if tag is None:
            raise TagServiceError(f"Unknown tag key: {key}")
        return tag

    def _require_web_id(self, tag: TagDefinition) -> str:
        if not tag.web_id:
            raise TagServiceError(
                f"Tag '{tag.name}' is configured but has no PI WebId yet. "
                "Add the approved WebId to the local tag configuration."
            )
        return tag.web_id

    async def current_value(self, key: str) -> dict[str, Any]:
        tag = self._require_tag(key)
        web_id = self._require_web_id(tag)
        try:
            value = await self.pi.current_value(web_id)
        except PIWebAPIError as exc:
            raise TagServiceError(str(exc)) from exc

        return {
            "tag": asdict(tag),
            "value": value,
        }

    async def recorded_values(
        self,
        key: str,
        start_time: str,
        end_time: str,
        max_count: int = 1000,
    ) -> dict[str, Any]:
        tag = self._require_tag(key)
        web_id = self._require_web_id(tag)
        try:
            values = await self.pi.recorded_values(
                web_id=web_id,
                start_time=start_time,
                end_time=end_time,
                max_count=max_count,
            )
        except PIWebAPIError as exc:
            raise TagServiceError(str(exc)) from exc

        return {
            "tag": asdict(tag),
            "range": {
                "start_time": start_time,
                "end_time": end_time,
                "max_count": max_count,
            },
            "data": values,
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        try:
            return [asdict(tag) for tag in self.registry.find(query)]
        except TagRegistryError as exc:
            raise TagServiceError(str(exc)) from exc
