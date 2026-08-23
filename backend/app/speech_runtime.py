from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


class SpeechRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpeechRuntimeStatus:
    ready: bool
    binary: str
    model: str
    language: str
    local_only: bool = True


def _candidate_binary() -> str:
    configured = os.environ.get("FCC_STT_BINARY", "").strip()
    if configured:
        return configured
    for name in ("whisper-cli", "main"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def _candidate_model() -> str:
    configured = os.environ.get("FCC_STT_MODEL", "").strip()
    if configured:
        return configured
    roots = [
        Path.home() / ".fcc-assistant" / "models",
        Path.cwd() / "models",
        Path.cwd() / "assets" / "models",
    ]
    names = (
        "ggml-large-v3-turbo-q5_0.bin",
        "ggml-large-v3-turbo.bin",
        "ggml-large-v3.bin",
    )
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.exists():
                return str(candidate)
    return ""


def runtime_status() -> SpeechRuntimeStatus:
    binary = _candidate_binary()
    model = _candidate_model()
    return SpeechRuntimeStatus(
        ready=bool(binary and Path(binary).exists() and model and Path(model).exists()),
        binary=binary,
        model=model,
        language=os.environ.get("FCC_STT_LANGUAGE", "el") or "el",
    )


def transcribe_wav(data: bytes, *, prompt: str = "") -> str:
    status = runtime_status()
    if not status.ready:
        raise SpeechRuntimeError(
            "Local speech runtime is not ready. Configure FCC_STT_BINARY and FCC_STT_MODEL."
        )
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SpeechRuntimeError("Speech input must be PCM WAV audio")

    with tempfile.TemporaryDirectory(prefix="fcc-stt-") as tmp:
        root = Path(tmp)
        wav_path = root / "speech.wav"
        output_base = root / "transcript"
        wav_path.write_bytes(data)

        command = [
            status.binary,
            "-m",
            status.model,
            "-f",
            str(wav_path),
            "-l",
            status.language,
            "-otxt",
            "-of",
            str(output_base),
            "-nt",
            "-np",
        ]
        clean_prompt = " ".join(prompt.split())[:1200]
        if clean_prompt:
            command.extend(["--prompt", clean_prompt])

        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=90,
                env={**os.environ, "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8")},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SpeechRuntimeError(f"Local speech runtime failed: {exc}") from exc

        txt_path = output_base.with_suffix(".txt")
        transcript = txt_path.read_text(encoding="utf-8").strip() if txt_path.exists() else ""
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "unknown whisper.cpp error"
            raise SpeechRuntimeError(detail[-2000:])
        if not transcript:
            raise SpeechRuntimeError("No speech was recognized")
        return transcript
