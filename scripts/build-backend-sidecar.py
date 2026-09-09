from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def require_modules(modules: dict[str, str]) -> None:
    missing = [package for module, package in modules.items() if importlib.util.find_spec(module) is None]
    if not missing:
        return
    packages = " ".join(missing)
    raise RuntimeError(
        "Missing backend build dependencies: "
        f"{', '.join(missing)}. Install the current backend requirements first with:\n"
        f"  {sys.executable} -m pip install -r backend/requirements.txt\n"
        f"or install the missing package(s):\n  {sys.executable} -m pip install {packages}"
    )


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

    # PyInstaller can otherwise complete successfully while an optional FastAPI
    # runtime dependency is absent, producing a sidecar that only fails when it
    # imports routes using Form/UploadFile. Fail before packaging instead.
    require_modules(
        {
            "PyInstaller": "pyinstaller",
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "multipart": "python-multipart",
        }
    )

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
        "--collect-submodules", "app",
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
