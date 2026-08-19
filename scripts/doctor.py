from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def command_version(command: str, args: list[str]) -> Check:
    executable = shutil.which(command)
    if not executable:
        return Check(command, False, "not installed or not on PATH")
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return Check(command, False, str(exc))
    output = (result.stdout or result.stderr).strip().splitlines()
    return Check(command, result.returncode == 0, output[0] if output else executable)


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    checks = [
        Check("Python 3.11+", sys.version_info >= (3, 11), sys.version.split()[0]),
        command_version("node", ["--version"]),
        command_version("npm", ["--version"]),
        command_version("rustc", ["--version"]),
        command_version("cargo", ["--version"]),
        command_version("ollama", ["--version"]),
        Check("backend requirements", (root / "backend" / "requirements.txt").exists(), str(root / "backend" / "requirements.txt")),
        Check("desktop package", (root / "desktop" / "package.json").exists(), str(root / "desktop" / "package.json")),
        Check("backend port 8000", port_open("127.0.0.1", 8000), "open" if port_open("127.0.0.1", 8000) else "not running"),
        Check("Ollama port 11434", port_open("127.0.0.1", 11434), "open" if port_open("127.0.0.1", 11434) else "not running"),
    ]

    print("FCC Assistant setup doctor\n")
    for item in checks:
        marker = "OK" if item.ok else "--"
        print(f"[{marker}] {item.name}: {item.detail}")

    required = checks[:5]
    if all(item.ok for item in required):
        print("\nCore development toolchain is available.")
    else:
        print("\nSome required development tools are missing.")

    print("\nJSON summary:")
    print(json.dumps([asdict(item) for item in checks], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
