from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.model_manager import LocalModelManager, ModelManagerError


async def main() -> int:
    manager = LocalModelManager()
    status = manager.status()
    print(f"Model: {status['name']}")
    print(f"Path: {status['path']}")
    if status["installed"] and manager.verify():
        print("Model is already installed and verified.")
        return 0

    print("Downloading official GGUF model. No FCC process data is uploaded.")
    try:
        result = await manager.install()
    except ModelManagerError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Installed and SHA-256 verified: {result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
