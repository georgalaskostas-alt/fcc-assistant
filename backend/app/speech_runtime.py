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
    managed = Path.home() / ".fcc-assistant" / "bin" / "whisper-cli"
    if managed.exists():
        return str(managed)
    for name in ("whisper-cli", "main"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def _candidate_model() -> str:
    configured = os.environ.get("FCC_STT_MODEL", "").strip()
    if configured:
        return configured
    roots = [Path.home() / ".fcc-assistant" / "models", Path.cwd() / "models", Path.cwd() / "assets" / "models"]
    # Prefer quantized turbo when present to reduce unified-memory pressure.
    names = ("ggml-large-v3-turbo-q5_0.bin", "ggml-large-v3-turbo.bin", "ggml-large-v3.bin")
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.exists():
                return str(candidate)
    return ""


def _language() -> str:
    configured = os.environ.get("FCC_STT_LANGUAGE", "el").strip().casefold()
    return "el" if configured in {"", "auto"} else configured


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(value, maximum))


def _threads() -> int:
    return _int_env("FCC_STT_THREADS", 4, 1, 8)


def _use_gpu() -> bool:
    # Qwen already occupies Metal/unified memory. CPU STT is the conservative
    # packaged-app default; capable workstations can opt in with FCC_STT_USE_GPU=1.
    return os.environ.get("FCC_STT_USE_GPU", "0").strip().casefold() in {"1", "true", "yes", "on"}


def runtime_status() -> SpeechRuntimeStatus:
    binary = _candidate_binary()
    model = _candidate_model()
    return SpeechRuntimeStatus(
        ready=bool(binary and Path(binary).exists() and model and Path(model).exists()),
        binary=binary,
        model=model,
        language=_language(),
    )


def transcribe_wav(data: bytes, *, prompt: str = "", high_accuracy: bool = False) -> str:
    status = runtime_status()
    if not status.ready:
        raise SpeechRuntimeError("Local speech runtime is not ready. Install whisper.cpp and a local model or configure FCC_STT_BINARY/FCC_STT_MODEL.")
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SpeechRuntimeError("Speech input must be PCM WAV audio")

    with tempfile.TemporaryDirectory(prefix="fcc-stt-") as tmp:
        root = Path(tmp)
        wav_path = root / "speech.wav"
        output_base = root / "transcript"
        wav_path.write_bytes(data)

        command = [
            status.binary, "-m", status.model, "-f", str(wav_path), "-l", status.language,
            "-t", str(_threads()), "-otxt", "-of", str(output_base), "-nt", "-np", "-nf",
        ]
        if not _use_gpu():
            command.append("-ng")
        # Keep decoding light. The domain normalizer handles refinery aliases;
        # beam search was causing unacceptable contention on the desktop target.
        if high_accuracy:
            command.extend(["--best-of", "2", "--temperature", "0"])

        clean_prompt = " ".join(prompt.split())[:700]
        if clean_prompt:
            command.extend(["--prompt", clean_prompt])

        timeout_seconds = _int_env("FCC_STT_TIMEOUT_SECONDS", 35, 10, 90)
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=timeout_seconds,
                env={**os.environ, "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8")},
            )
        except subprocess.TimeoutExpired as exc:
            raise SpeechRuntimeError(f"Local speech runtime timed out after {timeout_seconds}s; transcription was stopped to protect system responsiveness.") from exc
        except OSError as exc:
            raise SpeechRuntimeError(f"Local speech runtime could not start: {exc}") from exc

        txt_path = output_base.with_suffix(".txt")
        transcript = txt_path.read_text(encoding="utf-8").strip() if txt_path.exists() else ""
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic output"
            reason = f"signal {-completed.returncode}" if completed.returncode < 0 else f"exit {completed.returncode}"
            raise SpeechRuntimeError(f"Local speech runtime failed ({reason}): {detail[-1200:]}")
        if not transcript:
            raise SpeechRuntimeError("No speech was recognized")
        return transcript
