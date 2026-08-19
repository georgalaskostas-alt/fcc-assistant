from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from .settings import get_settings


class LocalAIError(RuntimeError):
    pass


SYSTEM_PROMPT = """You are FCC Assistant, a local read-only process analysis assistant.
Use only the process evidence supplied in the prompt. Never invent tag values, causes, alarms,
limits, or operating events. Clearly separate observed facts from calculated results and possible
engineering hypotheses. Do not recommend changing plant setpoints or controls. Current mode is
analysis and reporting only.
"""


@dataclass(frozen=True)
class LocalAIResponse:
    model: str
    text: str


def _is_local_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


class LocalAIClient:
    """FCC intelligence client with embedded llama.cpp by default and optional TRAVIS bridge."""

    def __init__(self) -> None:
        settings = get_settings()
        self.travis_url = settings.travis_ai_url.rstrip("/")
        self.travis_timeout = settings.travis_ai_timeout_seconds
        self.prefer_travis = settings.prefer_travis_ai

        self.base_url = settings.local_ai_url.rstrip("/")
        self.model = settings.local_ai_model_name.strip() or "embedded-local-model"
        self.timeout = settings.local_ai_timeout_seconds

        if self.travis_url and not _is_local_url(self.travis_url):
            raise LocalAIError("TRAVIS endpoint must be localhost only")
        if not _is_local_url(self.base_url):
            raise LocalAIError("External AI endpoints are blocked. Only localhost is allowed.")

    async def status(self) -> dict[str, Any]:
        if self.prefer_travis:
            try:
                async with httpx.AsyncClient(timeout=min(self.travis_timeout, 5.0)) as client:
                    response = await client.get(f"{self.travis_url}/v1/fcc/status")
                    response.raise_for_status()
                    payload = response.json()
                if isinstance(payload, dict):
                    return {
                        "configured": True,
                        "connected": True,
                        "runtime": "TRAVIS",
                        "provider": "TRAVIS",
                        "model": payload.get("model"),
                        "local_only_link": True,
                        "travis": payload,
                    }
            except (httpx.HTTPError, ValueError):
                pass

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {
                "configured": True,
                "connected": False,
                "runtime": "llama.cpp",
                "provider": "embedded-local",
                "model": self.model,
                "local_only": True,
                "detail": str(exc),
            }

        return {
            "configured": True,
            "connected": True,
            "runtime": "llama.cpp",
            "provider": "embedded-local",
            "model": self.model,
            "local_only": True,
            "health": payload,
        }

    async def generate(self, user_prompt: str, context: dict[str, Any] | None = None) -> LocalAIResponse:
        prompt = user_prompt.strip()
        if not prompt:
            raise LocalAIError("Prompt cannot be empty")

        if self.prefer_travis:
            try:
                return await self._generate_with_travis(prompt, context)
            except LocalAIError:
                pass

        return await self._generate_with_embedded(prompt, context)

    async def _generate_with_travis(self, prompt: str, context: dict[str, Any] | None) -> LocalAIResponse:
        if not self.travis_url or not _is_local_url(self.travis_url):
            raise LocalAIError("TRAVIS local bridge is not configured")
        body = {
            "source": "fcc-assistant",
            "mode": "read_only_process_analysis",
            "question": prompt,
            "system_prompt": SYSTEM_PROMPT,
            "evidence": context or {},
            "data_policy": "local_only_no_external_process_data",
        }
        try:
            async with httpx.AsyncClient(timeout=self.travis_timeout) as client:
                response = await client.post(f"{self.travis_url}/v1/fcc/analyze", json=body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIError(f"TRAVIS is not reachable: {exc}") from exc

        text = payload.get("answer") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LocalAIError("TRAVIS returned an empty or invalid response")
        model = payload.get("provider") if isinstance(payload, dict) else None
        return LocalAIResponse(model=str(model or "TRAVIS"), text=text.strip())

    async def _generate_with_embedded(self, prompt: str, context: dict[str, Any] | None) -> LocalAIResponse:
        evidence = f"\n\nPROCESS EVIDENCE (structured data):\n{context}\n" if context else ""
        body = {
            "model": self.model,
            "stream": False,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{prompt}{evidence}"},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/v1/chat/completions", json=body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIError(f"Embedded local AI request failed: {exc}") from exc

        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalAIError("Embedded local AI returned an invalid response") from exc

        if not isinstance(text, str) or not text.strip():
            raise LocalAIError("Embedded local AI returned an empty response")

        return LocalAIResponse(model=self.model, text=text.strip())
