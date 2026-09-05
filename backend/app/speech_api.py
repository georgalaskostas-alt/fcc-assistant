from __future__ import annotations

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
    return {
        **asdict(status),
        "engine": "whisper.cpp",
        "cloud": False,
        "audio_leaves_device": False,
        "confidence_semantics": "command confidence after domain normalization; not acoustic posterior probability",
    }


@router.post("/trace")
def speech_trace(request: VoiceTraceRequest) -> dict[str, object]:
    # Local-only observability hook used by the packaged desktop app. Keep the
    # payload bounded and never retain audio.
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
    """Return a tiny, non-authoritative context window for short follow-ups.

    It helps Whisper keep words such as «κάντα», «αυτά», «πάλι» intact without
    biasing the current utterance toward a unit that was not actually spoken.
    """
    try:
        state = DashboardDialogueStore().get_state(workspace)
    except (OSError, ValueError):
        return ""
    turns = state.get("recent_turns")
    if not isinstance(turns, list):
        return ""
    recent: list[str] = []
    for turn in turns[-2:]:
        if not isinstance(turn, dict):
            continue
        user = str(turn.get("user", "")).strip()
        if user:
            recent.append(user[:180])
    return " | ".join(recent)[:360]


@router.post("/transcribe")
async def speech_transcribe(
    audio: UploadFile = File(...),
    scope: str = Form(default="all"),
    terms_json: str = Form(default="[]"),
    mode: str = Form(default="final"),
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
    if normalized_mode == "partial":
        prompt = (
            "Ελληνική ομιλία με πιθανές αγγλικές τεχνικές λέξεις. "
            "Άκουσε ιδιαίτερα προσεκτικά τα ονόματα μονάδων: " + ", ".join(unit_terms) + "."
        )
    else:
        domain_terms = list(dict.fromkeys([*unit_terms, scope, *extra_terms]))[:40]
        prompt = (
            "Η ομιλία είναι στα Ελληνικά και μπορεί να περιέχει αγγλικούς refinery όρους. "
            "Απόδωσε πιστά ολόκληρη την τωρινή πρόταση. Μην αντικαθιστάς μία μονάδα με άλλη, "
            "μην συμπληρώνεις μονάδα που δεν ακούστηκε και μην εφευρίσκεις λέξεις. "
            "Διατήρησε τεχνικούς όρους και ακρωνύμια όπως FCC, HCU, Hydrocracker, feed flow, "
            "reactor temperature, regenerator, riser και stripper στην καθιερωμένη γραφή τους. "
            "Οι σύντομες φράσεις συνέχειας όπως κάντα, αυτά, εκείνα, πάλι, ίδια και τελικά είναι έγκυρες. "
            "Πιθανοί όροι: " + ", ".join(domain_terms)
        )
        if recent_context:
            prompt += (
                ". Πρόσφατο συνομιλιακό πλαίσιο μόνο για αναγνώριση αντωνυμιών/συνέχειας, "
                "όχι για να προσθέσεις πληροφορία που δεν ακούστηκε τώρα: " + recent_context
            )

    try:
        read_started = perf_counter()
        data = await audio.read()
        read_ms = round((perf_counter() - read_started) * 1000, 1)
        if len(data) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio clip is too large")

        stt_started = perf_counter()
        raw = transcribe_wav(data, prompt=prompt, high_accuracy=normalized_mode == "final")
        stt_ms = round((perf_counter() - stt_started) * 1000, 1)

        normalize_started = perf_counter()
        decision = normalize_transcript(raw, extra_terms=list(dict.fromkeys([*unit_terms, *extra_terms])))
        normalize_ms = round((perf_counter() - normalize_started) * 1000, 1)
    except SpeechRuntimeError as exc:
        append_trace("speech.error", {
            "mode": normalized_mode,
            "error": str(exc),
            "elapsed_ms": round((perf_counter() - request_started) * 1000, 1),
        })
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await audio.close()

    total_ms = round((perf_counter() - request_started) * 1000, 1)
    timings = {
        "read_ms": read_ms,
        "stt_ms": stt_ms,
        "normalize_ms": normalize_ms,
        "total_ms": total_ms,
    }
    result = {
        "raw_text": decision.raw_text,
        "text": decision.normalized_text,
        "confidence": decision.confidence,
        "confidence_level": decision.level,
        "execute_immediately": decision.execute_immediately,
        "corrections": [asdict(item) for item in decision.corrections],
        "scope": scope,
        "language": "el",
        "engine": "whisper.cpp",
        "mode": normalized_mode,
        "local_only": True,
        "audio_retained": False,
        "audio_bytes": len(data),
        "timings": timings,
    }
    if normalized_mode == "final":
        append_trace("speech.final", {
            "raw_text": decision.raw_text,
            "normalized_text": decision.normalized_text,
            "confidence": decision.confidence,
            "level": decision.level,
            "corrections": [asdict(item) for item in decision.corrections],
            "scope": scope,
            "audio_bytes": len(data),
            "timings": timings,
            "recent_context_used": bool(recent_context),
        })
    return result
