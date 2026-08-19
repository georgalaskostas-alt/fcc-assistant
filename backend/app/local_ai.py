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
limits, or operating events. Clearly separate observed facts from possible engineering hypotheses.
Do not recommend changing plant setpoints or controls unless an authorized engineering workflow
is added in a future version. Current mode is analysis and reporting only.
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
    """FCC intelligence client. TRAVIS is the preferred local brain.

    FCC never sends process evidence directly to an arbitrary external endpoint.
    It talks to TRAVIS on localhost. TRAVIS can then use its own local knowledge,
    learned skills, or its configured model fallback according to TRAVIS policy.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.travis_url = settings.travis_ai_url.rstrip("/")
        self.travis_timeout = settings.travis_ai_timeout_seconds
        self.prefer_travis = settings.prefer_travis_ai

        self.base_url = settings.local_ai_url.rstrip("/")
        self.model = settings.local_ai_model.strip()
        self.timeout = settings.local_ai_timeout_seconds

        if self.travis_url and not _is_local_url(self.travis_url):
            raise LocalAIError("TRAVIS endpoint must be localhost only")
        if self.base_url and not _is_local_url(self.base_url):
            raise LocalAIError("External AI endpoints are blocked. FCC Assistant only allows localhost AI runtimes.")

    async def status(self) -> dict[str, Any]:
        if self.prefer_travis:
            try:
                async with httpx.AsyncClient(timeout=min(self.travis_timeout, 10.0)) as client:
                    response = await client.get(f"{self.travis_url}/v1/fcc/status")
                    response.raise_for_status()
                    payload = response.json()
                if isinstance(payload, dict):
                    return {
                        "configured": True,
                        "connected": True,
                        "provider": "TRAVIS",
                        "model": payload.get("model"),
                        "local_only_link": True,
                        "travis": payload,
                    }
            except (httpx.HTTPError, ValueError):
                pass

        if not self.base_url:
            return {"configured": False, "connected": False, "model": self.model or None, "provider": "none"}
        self._ensure_local_endpoint()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIError(f"Neither TRAVIS nor the optional local AI fallback is reachable: {exc}") from exc
        models = []
        if isinstance(payload, dict) and isinstance(payload.get("models"), list):
            models = [item.get("name") for item in payload["models"] if isinstance(item, dict)]
        return {
            "configured": bool(self.model),
            "connected": True,
            "provider": "local-fallback",
            "model": self.model or None,
            "model_available": self.model in models if self.model else False,
            "available_models": models,
            "local_only": True,
        }

    def _ensure_local_endpoint(self) -> None:
        if self.base_url and not _is_local_url(self.base_url):
            raise LocalAIError("External AI endpoints are blocked")

    async def generate(self, user_prompt: str, context: dict[str, Any] | None = None) -> LocalAIResponse:
        prompt = user_prompt.strip()
        if not prompt:
            raise LocalAIError("Prompt cannot be empty")

        if self.prefer_travis:
            try:
                return await self._generate_with_travis(prompt, context)
            except LocalAIError:
                # Fall through only when the optional local fallback is explicitly configured.
                if not self.model:
                    raise

        return await self._generate_with_local_runtime(prompt, context)

    async def _generate_with_travis(self, prompt: str, context: dict[str, Any] | None) -> LocalAIResponse:
        if not self.travis_url or not _is_local_url(self.travis_url):
            raise LocalAIError("TRAVIS local bridge is not configured")
        body = {
            "source": "fcc-assistant",
            "mode": "read_only_process_analysis",
            "question": prompt,
            "system_prompt": SYSTEM_PROMPT,
            "evidence": context or {},
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

    async def _generate_with_local_runtime(self, prompt: str, context: dict[str, Any] | None) -> LocalAIResponse:
        if not self.base_url:
            raise LocalAIError("Local AI URL is not configured")
        self._ensure_local_endpoint()
        if not self.model:
            raise LocalAIError("TRAVIS is unavailable and no local fallback model is configured")

        evidence = f"\n\nPROCESS EVIDENCE (structured data):\n{context}\n" if context else ""
        body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{prompt}{evidence}"},
            ],
            "options": {"temperature": 0.1},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=body)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIError(f"Local AI request failed: {exc}") from exc
        message = payload.get("message") if isinstance(payload, dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LocalAIError("Local AI returned an empty or invalid response")
        return LocalAIResponse(model=self.model, text=text.strip())
