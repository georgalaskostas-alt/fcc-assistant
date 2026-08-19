from __future__ import annotations

import argparse
import platform
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage llama.cpp and a GGUF model for FCC Assistant packaging")
    parser.add_argument("--llama-server", required=True, help="Path to llama-server binary")
    parser.add_argument("--model", required=True, help="Path to GGUF model")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_binary = Path(args.llama_server).expanduser().resolve()
    source_model = Path(args.model).expanduser().resolve()

    if not source_binary.is_file():
        raise SystemExit(f"llama-server binary not found: {source_binary}")
    if not source_model.is_file() or source_model.suffix.lower() != ".gguf":
        raise SystemExit(f"GGUF model not found: {source_model}")

    binary_name = "llama-server.exe" if platform.system() == "Windows" else "llama-server"
    binary_target = root / "runtime" / "bin" / binary_name
    model_target = root / "models" / "default.gguf"

    binary_target.parent.mkdir(parents=True, exist_ok=True)
    model_target.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_binary, binary_target)
    shutil.copy2(source_model, model_target)

    if platform.system() != "Windows":
        binary_target.chmod(binary_target.stat().st_mode | 0o111)

    print("Embedded AI assets staged successfully")
    print(f"  runtime: {binary_target}")
    print(f"  model:   {model_target}")
    print("These files are intentionally ignored by Git and must not be committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
