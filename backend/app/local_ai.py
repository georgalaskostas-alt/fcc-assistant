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
    """Strictly local client for the embedded llama.cpp server."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.local_ai_url.rstrip("/")
        self.model = settings.local_ai_model_name.strip() or "embedded-local-model"
        self.timeout = settings.local_ai_timeout_seconds
        if not _is_local_url(self.base_url):
            raise LocalAIError("External AI endpoints are blocked. Only localhost is allowed.")

    async def status(self) -> dict[str, Any]:
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
                "model": self.model,
                "local_only": True,
                "detail": str(exc),
            }

        return {
            "configured": True,
            "connected": True,
            "runtime": "llama.cpp",
            "model": self.model,
            "local_only": True,
            "health": payload,
        }

    async def generate(self, user_prompt: str, context: dict[str, Any] | None = None) -> LocalAIResponse:
        prompt = user_prompt.strip()
        if not prompt:
            raise LocalAIError("Prompt cannot be empty")

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
