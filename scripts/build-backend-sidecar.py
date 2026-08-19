from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def host_triple() -> str:
    result = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        capture_output=True,
        text=True,
        check=True,
    )
    triple = result.stdout.strip()
    if not triple:
        raise RuntimeError("Could not determine Rust host target triple")
    return triple


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    backend = root / "backend"
    tauri_binaries = root / "desktop" / "src-tauri" / "binaries"
    build_root = root / ".build" / "backend-sidecar"
    dist = build_root / "dist"
    work = build_root / "work"
    spec = build_root / "spec"

    tauri_binaries.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name", "fcc-backend",
        "--paths", str(backend),
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(spec),
        str(backend / "entrypoint.py"),
    ], root)

    extension = ".exe" if platform.system() == "Windows" else ""
    source = dist / f"fcc-backend{extension}"
    if not source.exists():
        raise RuntimeError(f"PyInstaller output missing: {source}")

    target = tauri_binaries / f"fcc-backend-{host_triple()}{extension}"
    shutil.copy2(source, target)
    if platform.system() != "Windows":
        target.chmod(target.stat().st_mode | 0o111)

    print(f"Backend sidecar staged: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
