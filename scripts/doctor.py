from __future__ import annotations

import ctypes
import json
import platform
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
            timeout=8,
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


def memory_gb() -> float | None:
    system = platform.system()
    try:
        if system == "Windows":
            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MemoryStatusEx()
            status.dwLength = ctypes.sizeof(MemoryStatusEx)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return round(status.ullTotalPhys / (1024 ** 3), 1)
        if system == "Darwin":
            result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return round(int(result.stdout.strip()) / (1024 ** 3), 1)
        if hasattr(__import__("os"), "sysconf"):
            import os
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round((pages * page_size) / (1024 ** 3), 1)
    except Exception:
        return None
    return None


def gpu_name() -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Chipset Model:"):
                    return stripped.split(":", 1)[1].strip()
        elif system == "Windows":
            powershell = shutil.which("powershell") or shutil.which("pwsh")
            if powershell:
                result = subprocess.run(
                    [powershell, "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; '"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                )
                value = result.stdout.strip()
                if value:
                    return value
        else:
            nvidia = shutil.which("nvidia-smi")
            if nvidia:
                result = subprocess.run(
                    [nvidia, "--query-gpu=name", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if result.stdout.strip():
                    return "; ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
    except Exception:
        pass
    return "not detected"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    backend_running = port_open("127.0.0.1", 8000)
    ollama_running = port_open("127.0.0.1", 11434)

    hardware = {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu": platform.processor() or platform.machine(),
        "logical_cpu_count": __import__("os").cpu_count(),
        "ram_gb": memory_gb(),
        "gpu": gpu_name(),
    }

    checks = [
        Check("Python 3.11+", sys.version_info >= (3, 11), sys.version.split()[0]),
        command_version("node", ["--version"]),
        command_version("npm", ["--version"]),
        command_version("rustc", ["--version"]),
        command_version("cargo", ["--version"]),
        command_version("ollama", ["--version"]),
        Check("backend requirements", (root / "backend" / "requirements.txt").exists(), str(root / "backend" / "requirements.txt")),
        Check("desktop package", (root / "desktop" / "package.json").exists(), str(root / "desktop" / "package.json")),
        Check("backend port 8000", backend_running, "open" if backend_running else "not running"),
        Check("Ollama port 11434", ollama_running, "open" if ollama_running else "not running"),
    ]

    print("FCC Assistant setup doctor\n")
    print("Hardware")
    for key, value in hardware.items():
        print(f"  {key}: {value}")

    print("\nToolchain")
    for item in checks:
        marker = "OK" if item.ok else "--"
        print(f"[{marker}] {item.name}: {item.detail}")

    required = checks[:5]
    if all(item.ok for item in required):
        print("\nCore development toolchain is available.")
    else:
        print("\nSome required development tools are missing.")

    print("\nJSON summary:")
    print(json.dumps({"hardware": hardware, "checks": [asdict(item) for item in checks]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
