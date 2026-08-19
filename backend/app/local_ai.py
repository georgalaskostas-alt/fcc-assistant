from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


class LocalAIClient:
    """Client for a local Ollama-compatible runtime on the user's laptop."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.local_ai_url.rstrip("/")
        self.model = settings.local_ai_model.strip()
        self.timeout = settings.local_ai_timeout_seconds

    def _ensure_configured(self) -> None:
        if not self.base_url:
            raise LocalAIError("Local AI URL is not configured")
        if not self.model:
            raise LocalAIError("Local AI model is not configured")

    async def status(self) -> dict[str, Any]:
        if not self.base_url:
            return {"configured": False, "connected": False, "model": self.model or None}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIError(f"Local AI runtime is not reachable: {exc}") from exc

        models = []
        if isinstance(payload, dict) and isinstance(payload.get("models"), list):
            models = [item.get("name") for item in payload["models"] if isinstance(item, dict)]

        return {
            "configured": bool(self.model),
            "connected": True,
            "model": self.model or None,
            "model_available": self.model in models if self.model else False,
            "available_models": models,
        }

    async def generate(self, user_prompt: str, context: dict[str, Any] | None = None) -> LocalAIResponse:
        self._ensure_configured()
        prompt = user_prompt.strip()
        if not prompt:
            raise LocalAIError("Prompt cannot be empty")

        evidence = ""
        if context:
            evidence = f"\n\nPROCESS EVIDENCE (structured data):\n{context}\n"

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
