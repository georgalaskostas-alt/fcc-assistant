from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
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
    ready: bool = False
    detail: str | None = None


class EmbeddedAIRuntime:
    """Owns and supervises the local llama.cpp server used by FCC Assistant."""

    _process: subprocess.Popen[Any] | None = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(__file__).resolve().parents[2]
        self.binary_path = self._resolve_binary_path(self.settings.local_ai_binary_path)
        self.model_path = self._resolve_path(self.settings.local_ai_model_path)
        self.cache_dir = Path.home() / ".fcc-assistant" / "cache" / "llama.cpp"
        self.log_dir = Path.home() / ".fcc-assistant" / "logs"
        self.endpoint = self.settings.local_ai_url
        parsed = urlparse(self.endpoint)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise EmbeddedRuntimeError("Embedded AI endpoint must be localhost")
        self.host = "127.0.0.1"
        self.port = parsed.port or 8081

    def _resolve_path(self, configured: str) -> Path:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else self.root / path

    def _resolve_binary_path(self, configured: str) -> Path:
        path = self._resolve_path(configured)
        if platform.system() == "Windows" and path.suffix.lower() != ".exe":
            path = path.with_suffix(".exe")
        return path

    def _port_ready(self, timeout: float = 0.2) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def readiness(self) -> dict[str, Any]:
        return {
            "runtime": "llama.cpp",
            "local_only": True,
            "binary_present": self.binary_path.exists(),
            "model_present": self.model_path.exists(),
            "endpoint_ready": self._port_ready(),
            "binary_path": str(self.binary_path),
            "model_path": str(self.model_path),
            "endpoint": self.endpoint,
            "platform": platform.system(),
            "architecture": platform.machine(),
        }

    def state(self) -> RuntimeState:
        process = type(self)._process
        owned_running = process is not None and process.poll() is None
        endpoint_ready = self._port_ready()
        return RuntimeState(
            running=owned_running or endpoint_ready,
            pid=process.pid if owned_running and process is not None else None,
            binary_path=str(self.binary_path),
            model_path=str(self.model_path),
            endpoint=self.endpoint,
            ready=endpoint_ready,
            detail="external-or-existing-local-runtime" if endpoint_ready and not owned_running else None,
        )

    def start(self, wait_seconds: float = 20.0) -> RuntimeState:
        current = self.state()
        if current.ready:
            return current
        if not self.binary_path.exists():
            raise EmbeddedRuntimeError(f"Local llama.cpp binary not found: {self.binary_path}")
        if not self.model_path.exists():
            raise EmbeddedRuntimeError(f"Local GGUF model not found: {self.model_path}")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.binary_path),
            "-m", str(self.model_path),
            "--host", self.host,
            "--port", str(self.port),
            "-c", str(self.settings.local_ai_context_size),
        ]
        if self.settings.local_ai_threads > 0:
            command.extend(["-t", str(self.settings.local_ai_threads)])

        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        log_path = self.log_dir / "llama-server.log"
        log_handle = log_path.open("ab")
        type(self)._process = subprocess.Popen(
            command,
            cwd=str(self.binary_path.parent),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env={**os.environ, "LLAMA_CACHE": str(self.cache_dir)},
            creationflags=creationflags,
        )

        deadline = time.monotonic() + max(0.5, wait_seconds)
        while time.monotonic() < deadline:
            process = type(self)._process
            if process is not None and process.poll() is not None:
                raise EmbeddedRuntimeError(f"llama.cpp exited during startup; see {log_path}")
            if self._port_ready(timeout=0.15):
                return self.state()
            time.sleep(0.2)
        raise EmbeddedRuntimeError(f"llama.cpp did not become ready within {wait_seconds:.0f}s; see {log_path}")

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
