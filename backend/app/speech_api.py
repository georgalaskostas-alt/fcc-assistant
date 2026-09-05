from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from time import perf_counter

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .dashboard_dialogue import DashboardDialogueStore
from .diagnostic_trace import append_trace
from .site_model import load_site_model
from .speech_domain import normalize_transcript
from .speech_runtime import SpeechRuntimeError, runtime_status, transcribe_wav

router = APIRouter(prefix="/api/v1/speech", tags=["local-speech"])


class VoiceTraceRequest(BaseModel):
    stage: str = Field(min_length=1, max_length=80)
    payload: dict[str, object] = Field(default_factory=dict)


@router.get("/status")
def speech_status() -> dict[str, object]:
    status = runtime_status()
    return {**asdict(status), "engine": "whisper.cpp", "cloud": False, "audio_leaves_device": False,
            "confidence_semantics": "command confidence after domain normalization; not acoustic posterior probability"}


@router.post("/trace")
def speech_trace(request: VoiceTraceRequest) -> dict[str, object]:
    safe_payload = {str(k)[:80]: v for k, v in list(request.payload.items())[:24]}
    append_trace(f"voice.{request.stage.strip().casefold()}", safe_payload)
    return {"ok": True, "local_only": True}


def _unit_vocabulary() -> list[str]:
    try:
        site = load_site_model()
    except (ValueError, OSError):
        return ["FCC", "HCU", "Hydrocracker", "hydro cracker"]
    terms: list[str] = []
    for unit in site.units:
        terms.extend([unit.key, unit.name, *getattr(unit, "aliases", ())])
        if unit.key.casefold() == "hcu" or unit.name.casefold() == "hcu":
            terms.extend(["Hydrocracker", "hydro cracker", "hydrocracking", "υδροκράκερ", "υδροκρακερ"])
        if unit.key.casefold() == "vdu" or unit.name.casefold() == "vdu":
            terms.extend(["Vacuum Distillation", "vacuum unit", "μονάδα κενού", "μοναδα κενου"])
    terms.extend(DashboardDialogueStore().aliases().keys())
    return list(dict.fromkeys(term.strip() for term in terms if term.strip()))[:32]


def _recent_conversation_context(workspace: str = "default") -> str:
    try:
        state = DashboardDialogueStore().get_state(workspace)
    except (OSError, ValueError):
        return ""
    turns = state.get("recent_turns")
    if not isinstance(turns, list):
        return ""
    recent: list[str] = []
    for turn in turns[-2:]:
        if isinstance(turn, dict):
            user = str(turn.get("user", "")).strip()
            if user:
                recent.append(user[:180])
    return " | ".join(recent)[:360]


@router.post("/transcribe")
async def speech_transcribe(
    audio: UploadFile = File(...), scope: str = Form(default="all"),
    terms_json: str = Form(default="[]"), mode: str = Form(default="final"),
) -> dict[str, object]:
    request_started = perf_counter()
    try:
        parsed = json.loads(terms_json)
        extra_terms = [str(value) for value in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        extra_terms = []

    normalized_mode = mode.strip().casefold()
    if normalized_mode not in {"partial", "final"}:
        normalized_mode = "final"
    unit_terms = _unit_vocabulary()
    recent_context = _recent_conversation_context() if normalized_mode == "final" else ""
    domain_terms = list(dict.fromkeys([*unit_terms, scope, *extra_terms]))[:40]
    prompt = (
        "Ελληνική ομιλία με πιθανές αγγλικές τεχνικές λέξεις. Απόδωσε πιστά μόνο την τωρινή πρόταση. "
        "Μην προσθέτεις μονάδα που δεν ακούστηκε. Διατήρησε FCC, HCU, Hydrocracker, feed flow, "
        "reactor temperature, regenerator, riser, stripper. Πιθανοί όροι: " + ", ".join(domain_terms)
    )
    if recent_context and normalized_mode == "final":
        prompt += ". Πρόσφατο πλαίσιο μόνο για αντωνυμίες, όχι για προσθήκη πληροφορίας: " + recent_context

    try:
        read_started = perf_counter()
        data = await audio.read()
        read_ms = round((perf_counter() - read_started) * 1000, 1)
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio clip is too large")

        stt_started = perf_counter()
        # whisper-cli is blocking/native work. Running it in a worker keeps the
        # FastAPI loop responsive for health, diagnostics and UI requests.
        raw = await asyncio.to_thread(
            transcribe_wav, data, prompt=prompt, high_accuracy=normalized_mode == "final"
        )
        stt_ms = round((perf_counter() - stt_started) * 1000, 1)

        normalize_started = perf_counter()
        decision = normalize_transcript(raw, extra_terms=list(dict.fromkeys([*unit_terms, *extra_terms])))
        normalize_ms = round((perf_counter() - normalize_started) * 1000, 1)
    except SpeechRuntimeError as exc:
        append_trace("speech.error", {"mode": normalized_mode, "error": str(exc),
                                      "elapsed_ms": round((perf_counter() - request_started) * 1000, 1)})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await audio.close()

    total_ms = round((perf_counter() - request_started) * 1000, 1)
    timings = {"read_ms": read_ms, "stt_ms": stt_ms, "normalize_ms": normalize_ms, "total_ms": total_ms}
    result = {
        "raw_text": decision.raw_text, "text": decision.normalized_text,
        "confidence": decision.confidence, "confidence_level": decision.level,
        "execute_immediately": decision.execute_immediately,
        "corrections": [asdict(item) for item in decision.corrections], "scope": scope,
        "language": "el", "engine": "whisper.cpp", "mode": normalized_mode,
        "local_only": True, "audio_retained": False, "audio_bytes": len(data), "timings": timings,
    }
    if normalized_mode == "final":
        append_trace("speech.final", {
            "raw_text": decision.raw_text, "normalized_text": decision.normalized_text,
            "confidence": decision.confidence, "level": decision.level,
            "corrections": [asdict(item) for item in decision.corrections], "scope": scope,
            "audio_bytes": len(data), "timings": timings, "recent_context_used": bool(recent_context),
        })
    return result
