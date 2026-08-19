from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .settings import get_settings


class EmbeddedRuntimeError(RuntimeError):
    pass


@dataclass
class RuntimeState:
    running: bool
    pid: int | None
    binary_path: str
    model_path: str
    endpoint: str
    runtime: str = "llama.cpp"
    local_only: bool = True


class EmbeddedAIRuntime:
    """Owns the bundled llama.cpp server process used by FCC Assistant."""

    _process: subprocess.Popen[Any] | None = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(__file__).resolve().parents[2]
        self.binary_path = self._resolve_binary_path(self.settings.local_ai_binary_path)
        self.model_path = self._resolve_path(self.settings.local_ai_model_path)
        self.endpoint = self.settings.local_ai_url
        parsed = urlparse(self.endpoint)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise EmbeddedRuntimeError("Embedded AI endpoint must be localhost")
        self.port = parsed.port or 8081

    def _resolve_path(self, configured: str) -> Path:
        path = Path(configured)
        return path if path.is_absolute() else self.root / path

    def _resolve_binary_path(self, configured: str) -> Path:
        path = self._resolve_path(configured)
        if platform.system() == "Windows" and path.suffix.lower() != ".exe":
            path = path.with_suffix(".exe")
        return path

    def readiness(self) -> dict[str, Any]:
        return {
            "runtime": "llama.cpp",
            "local_only": True,
            "binary_present": self.binary_path.exists(),
            "model_present": self.model_path.exists(),
            "binary_path": str(self.binary_path),
            "model_path": str(self.model_path),
            "endpoint": self.endpoint,
            "platform": platform.system(),
            "architecture": platform.machine(),
        }

    def state(self) -> RuntimeState:
        process = type(self)._process
        running = process is not None and process.poll() is None
        return RuntimeState(
            running=running,
            pid=process.pid if running and process is not None else None,
            binary_path=str(self.binary_path),
            model_path=str(self.model_path),
            endpoint=self.endpoint,
        )

    def start(self) -> RuntimeState:
        current = self.state()
        if current.running:
            return current
        if not self.binary_path.exists():
            raise EmbeddedRuntimeError(f"Bundled llama.cpp binary not found: {self.binary_path}")
        if not self.model_path.exists():
            raise EmbeddedRuntimeError(f"Local GGUF model not found: {self.model_path}")

        command = [
            str(self.binary_path),
            "-m", str(self.model_path),
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "-c", str(self.settings.local_ai_context_size),
        ]
        if self.settings.local_ai_threads > 0:
            command.extend(["-t", str(self.settings.local_ai_threads)])

        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        type(self)._process = subprocess.Popen(
            command,
            cwd=str(self.root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "LLAMA_CACHE": str(self.root / "runtime" / "cache")},
            creationflags=creationflags,
        )
        return self.state()

    def stop(self) -> RuntimeState:
        process = type(self)._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        type(self)._process = None
        return self.state()
