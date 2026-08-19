from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx

from .settings import get_settings


class ModelManagerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagedModel:
    name: str
    url: str
    sha256: str
    size_bytes: int
    path: Path


QWEN3_4B_Q4_K_M = {
    "name": "Qwen3-4B-Q4_K_M",
    "url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true",
    "sha256": "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
    "size_bytes": 2_500_000_000,
}


class LocalModelManager:
    """Downloads only model weights; FCC process data is never uploaded."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = ManagedModel(
            name=QWEN3_4B_Q4_K_M["name"],
            url=QWEN3_4B_Q4_K_M["url"],
            sha256=QWEN3_4B_Q4_K_M["sha256"],
            size_bytes=QWEN3_4B_Q4_K_M["size_bytes"],
            path=Path(settings.local_ai_model_path).expanduser(),
        )

    def status(self) -> dict[str, object]:
        installed = self.model.path.exists()
        size = self.model.path.stat().st_size if installed else 0
        return {
            "name": self.model.name,
            "installed": installed,
            "path": str(self.model.path),
            "size_bytes": size,
            "expected_size_bytes": self.model.size_bytes,
            "download_source": "Hugging Face / Qwen official GGUF",
            "network_use": "model-download-only",
            "process_data_uploaded": False,
        }

    def verify(self, path: Path | None = None) -> bool:
        target = path or self.model.path
        if not target.exists():
            return False
        digest = hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().lower() == self.model.sha256.lower()

    async def install(self) -> dict[str, object]:
        self.model.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.model.path.with_suffix(self.model.path.suffix + ".part")
        if temp.exists():
            temp.unlink()

        try:
            async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
                async with client.stream("GET", self.model.url) as response:
                    response.raise_for_status()
                    with temp.open("wb") as handle:
                        async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                            handle.write(chunk)
        except (httpx.HTTPError, OSError) as exc:
            if temp.exists():
                temp.unlink()
            raise ModelManagerError(f"Model download failed: {exc}") from exc

        if not self.verify(temp):
            temp.unlink(missing_ok=True)
            raise ModelManagerError("Downloaded model failed SHA-256 verification")

        temp.replace(self.model.path)
        return self.status()

    def remove(self) -> dict[str, object]:
        self.model.path.unlink(missing_ok=True)
        return self.status()
