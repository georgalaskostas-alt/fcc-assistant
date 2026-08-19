from __future__ import annotations

from typing import Any

import httpx

from .settings import get_settings


class PIWebAPIError(RuntimeError):
    pass


class PIWebAPIClient:
    """Minimal read-only PI Web API client."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.pi_web_api_url.rstrip("/")
        self.verify_tls = settings.pi_verify_tls
        self.timeout = settings.pi_timeout_seconds

    def _ensure_configured(self) -> None:
        if not self.base_url:
            raise PIWebAPIError("PI Web API URL is not configured")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_configured()
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            async with httpx.AsyncClient(
                verify=self.verify_tls,
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PIWebAPIError(f"PI Web API request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise PIWebAPIError("PI Web API returned a non-JSON response") from exc

        if not isinstance(payload, dict):
            raise PIWebAPIError("Unexpected PI Web API response format")

        return payload

    async def root(self) -> dict[str, Any]:
        return await self._get("")

    async def current_value(self, web_id: str) -> dict[str, Any]:
        return await self._get(f"streams/{web_id}/value")

    async def recorded_values(
        self,
        web_id: str,
        start_time: str,
        end_time: str,
        max_count: int = 1000,
    ) -> dict[str, Any]:
        return await self._get(
            f"streams/{web_id}/recorded",
            params={
                "startTime": start_time,
                "endTime": end_time,
                "maxCount": max_count,
            },
        )
